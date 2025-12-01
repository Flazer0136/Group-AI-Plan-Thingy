import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from decimal import Decimal
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    @sync_to_async
    def track_room_visit(self, username):
        from django.contrib.auth.models import User
        from .models import RoomVisit
        try:
            user = User.objects.get(username=username)
            room_visit, created = RoomVisit.objects.update_or_create(
                user=user,
                room=self.room_name,
                defaults={'last_visited': timezone.now()}
            )
        except User.DoesNotExist:
            pass

    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        user = self.scope.get('user')
        if user and user.is_authenticated:
            display_name = user.username
            await self.track_room_visit(user.username)
        else:
            display_name = "Anonymous"

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': f'👋 {display_name} joined the chat!',
                'username': 'System',
                'system': True,
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        user = self.scope.get('user')
        if user and user.is_authenticated:
            display_name = user.username
        else:
            display_name = "Anonymous"

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': f'👋 {display_name} left the chat',
                'username': 'System',
                'system': True,
            }
        )

    @sync_to_async
    def save_message(self, room, username, content):
        from django.contrib.auth.models import User
        from .models import Message
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
            
        return Message.objects.create(
            room=room,
            author=user,
            content=content,
        )
    
    @sync_to_async
    def save_ai_message(self, room, content):
        from django.contrib.auth.models import User
        from .models import Message
        ai_user, created = User.objects.get_or_create(
            username='AI',
            defaults={'first_name': 'AI', 'last_name': 'Assistant', 'is_active': False}
        )
        return Message.objects.create(
            room=room,
            author=ai_user,
            content=content,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data.get('type') == 'ai_request':
            await self.handle_ai_request()
            return
        
        message = data['message']
        username = data.get('username', 'Anonymous')
        
        await self.save_message(self.room_name, username, message)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'system': False,
            }
        )

    async def handle_ai_request(self):
        total_cost = await self.get_total_cost()
        if total_cost >= 10.0:
            await self.send_system_message(
                "AI usage limit reached ($10). Please try again later."
            )
            return
        
        messages_list = await self.get_room_messages_values()
        
        # Check if there's any conversation
        conversation = await sync_to_async(self.prepare_conversation_context)(messages_list)
        if not conversation:
            await self.send_system_message(
                "There are no messages yet in this room. Start the conversation, then ask AI."
            )
            return
        
        # Check if last message was from AI and same user is asking again
        last_msg = messages_list[-1] if messages_list else None
        current_user = self.scope.get('user')
        requesting_username = (
            current_user.username if current_user and current_user.is_authenticated
            else "Anonymous"
        )

        if last_msg and last_msg["author__username"] == "AI":
            # Find the last human message before the AI reply
            last_human_msg = None
            for msg in reversed(messages_list):
                if msg["author__username"] not in ["AI", "System"]:
                    last_human_msg = msg
                    break

            # If the same user who prompted AI is asking again immediately
            if last_human_msg and last_human_msg["author__username"] == requesting_username:
                await self.send_system_message(
                    f"AI just responded to you, {requesting_username}. "
                    "Read the answer, add more details, or let others reply before asking again."
                )
                return

        # Generate AI response
        ai_response = await self.generate_ai_response(messages_list)

        # If generate_ai_response returns a generic error string, send it as system message
        if ai_response.startswith("Error:") or ai_response.startswith("Sorry"):
            await self.send_system_message(
                "There was a problem generating an AI response. Please try again."
            )
            return

        await self.save_ai_message(self.room_name, ai_response)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": ai_response,
                "username": "AI",
                "system": False,
            }
        )


    @sync_to_async
    def get_room_messages_values(self):
        from .models import Message
        messages = Message.objects.filter(room=self.room_name).order_by('timestamp')
        return list(messages.values('author__username', 'content', 'timestamp'))
    
    @sync_to_async
    def save_token_usage(self, prompt_tokens, response_tokens, total_tokens, cost_usd):
        from .models import AITokenUsage
        return AITokenUsage.objects.create(
            room=self.room_name,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd
        )
    
    @sync_to_async
    def get_total_cost(self):
        from .models import AITokenUsage
        from django.db.models import Sum
        result = AITokenUsage.objects.aggregate(total=Sum('cost_usd'))
        return float(result['total'] or 0)

    async def send_system_message(self, text):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': text,
                'username': 'System',
                'system': True,
            }
        )

    async def generate_ai_response(self, messages_data):
        from google import genai
        from google.genai import types
        
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return "Sorry, GEMINI_API_KEY is not configured."
            
            client = genai.Client(api_key=api_key)
            
            # Prepare conversation with role-based context
            conversation = await sync_to_async(self.prepare_conversation_context)(messages_data)
            
            # Build messages for Gemini
            gemini_messages = []
            
            # System instruction (concise planning assistant)
            system_instruction = """
            You are a helpful AI assistant for group planning and travel.
            
            Rules:
            - Keep responses SHORT (2-4 sentences) unless asked for detailed plan
            - When asked "help plan X", provide structured steps
            - Use **bold** and bullet points for readability
            - Be specific with recommendations when requested
            - Don't summarize conversation history back to users
            """
            
            # Add conversation history with proper roles
            for msg in conversation:
                gemini_messages.append(
                    types.Content(
                        role=msg['role'],
                        parts=[types.Part(text=msg['content'])]
                    )
                )
            
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=gemini_messages,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=200  # Keep responses concise
                )
            )
        
            
            # Token Usage Tracking
            usage = response.usage_metadata
            if usage:
                prompt_tokens = usage.prompt_token_count
                response_tokens = usage.candidates_token_count
                total_tokens = usage.total_token_count
                
                input_cost = (prompt_tokens / 1_000_000) * 0.075
                output_cost = (response_tokens / 1_000_000) * 0.30
                total_cost = input_cost + output_cost
                
                await self.save_token_usage(
                    prompt_tokens=prompt_tokens,
                    response_tokens=response_tokens,
                    total_tokens=total_tokens,
                    cost_usd=Decimal(str(total_cost))
                )
            
            return response.text
        except Exception as e:
            return f"Error: {str(e)}"
        

    def prepare_conversation_context(self, messages_data, max_messages=30):
        """Helper to prepare context"""
        if not messages_data:
            return []
        
        sorted_messages = sorted(messages_data, key=lambda x: x['timestamp'])
        recent_messages = sorted_messages[-max_messages:]
        
        conversation = []
        for msg in recent_messages:
            username = msg['author__username']
            content = msg['content']
            
            if username == 'System':
                continue
            
            if username == 'AI':
                conversation.append({'role': 'model', 'content': content})
            else:
                conversation.append({'role': 'user', 'content': f"{username}: {content}"})
        
        return conversation

    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'username': event.get('username', 'System'),
                'system': event.get('system', False),
            }))
        except Exception:
            pass