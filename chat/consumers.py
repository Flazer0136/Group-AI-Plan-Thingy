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
            # Create or update the room visit
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
        # Get user again to display name
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
        user = User.objects.get(username=username)
        return Message.objects.create(
            room=room,
            author=user,
            content=content,
        )
    
    @sync_to_async
    def save_ai_message(self, room, content):
        from django.contrib.auth.models import User
        from .models import Message
        # Only create AI user if it doesn't exist
        ai_user, created = User.objects.get_or_create(
            username='AI',
            defaults={
                'first_name': 'AI',
                'last_name': 'Assistant',
                'is_active': False,  # Mark as not a real user
            }
        )
        return Message.objects.create(
            room=room,
            author=ai_user,
            content=content,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Check if this is an AI request
        if data.get('type') == 'ai_request':
            await self.handle_ai_request()
            return
        
        # Otherwise, handle normal message
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
        # Check if we've hit the limit
        total_cost = await self.get_total_cost()
        if total_cost >= 10.0:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': '⚠️ AI usage limit reached ($10). Please contact admin.',
                    'username': 'System',
                    'system': True,
                }
            )
            return
        
        # Get all messages from the room
        messages = await self.get_room_messages()
        
        # Generate AI response
        ai_response = await self.generate_ai_response(messages)

        await self.save_ai_message(self.room_name, ai_response)
        
        # Broadcast AI response
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': ai_response,
                'username': 'AI',
                'system': False,
            }
        )

    @sync_to_async
    def get_room_messages(self):
        from .models import Message
        messages = Message.objects.filter(room=self.room_name).order_by('timestamp')
        return list(messages.values('author__username', 'content'))
    
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
    
    async def generate_ai_response(self, messages):
    # Import here to avoid Python 3.14 compatibility issues
        from google.genai import types
        from google import genai
        
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return "Sorry, GEMINI_API_KEY is not configured."
            
            client = genai.Client(api_key=api_key)
            
            # Build conversation with proper roles
            gemini_messages = []
            
            # Add system instruction first (optional but helpful)
            gemini_messages.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text="You are a helpful AI assistant in a chat room. Keep responses concise and friendly.")]
                )
            )
            gemini_messages.append(
                types.Content(
                    role="model",
                    parts=[types.Part(text="Understood! I'll be a helpful and concise assistant.")]
                )
            )
            
            # Add conversation history with proper roles
            for msg in messages:
                if msg['author__username'] == 'AI':
                    # AI's previous responses - use "model" role
                    gemini_messages.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=msg['content'])]
                        )
                    )
                else:
                    # User messages - use "user" role
                    gemini_messages.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=f"{msg['author__username']}: {msg['content']}")]
                        )
                    )
            
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=gemini_messages
            )
            
            # Extract token usage
            usage = response.usage_metadata
            prompt_tokens = usage.prompt_token_count
            response_tokens = usage.candidates_token_count
            total_tokens = usage.total_token_count
            
            # Calculate cost (Gemini 2.0 Flash pricing)
            # Input: $0.075 per 1M tokens, Output: $0.30 per 1M tokens
            input_cost = (prompt_tokens / 1_000_000) * 0.075
            output_cost = (response_tokens / 1_000_000) * 0.30
            total_cost = input_cost + output_cost
            
            # Save token usage
            await self.save_token_usage(
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens,
                cost_usd=Decimal(str(total_cost))
            )
            
            return response.text
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

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

    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'username': event.get('username', 'System'),
                'system': event.get('system', False),
            }))
        except Exception as e:
            # Connection already closed, ignore the error
            pass
