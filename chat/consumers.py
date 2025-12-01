import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from decimal import Decimal
from django.utils import timezone
from .utils import analyze_and_format_chat

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
            await self.send_system_message('⚠️ AI usage limit reached ($10).')
            return
        
        messages_list = await self.get_room_messages_values()
        optimized_context = await sync_to_async(analyze_and_format_chat)(messages_list)

        print("\n" + "="*40)
        print("🔍 PANDAS SUMMARY GENERATED (SENDING TO AI):")
        print("="*40)
        print(optimized_context)
        print("="*40 + "\n")
        
        ai_response = await self.generate_ai_response(optimized_context)

        await self.save_ai_message(self.room_name, ai_response)
        
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

    # =========================================================
    #  UPDATED AI GENERATION LOGIC (Better Persona)
    # =========================================================
    async def generate_ai_response(self, context_text):
        from google import genai
        from google.genai import types
        
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return "Sorry, GEMINI_API_KEY is not configured."
            
            client = genai.Client(api_key=api_key)
            
            # --- THE NEW SYSTEM PROMPT ---
            system_instruction = """
            You are a proactive and knowledgeable Travel Consultant & Project Manager.
            
            Your Rules:
            1. READ the log provided (it is compressed/keyword-only).
            2. IDENTIFY the current goal or decision.
            3. PROVIDE SPECIFIC RECOMMENDATIONS. Do not tell the user to "research X". YOU provide the research. Suggest specific cities, hotels, activities, or itineraries that fit their budget.
            4. IF they made a decision: Create a DETAILED Action Plan with specific steps.
            5. IF they are undecided: Pitch specific options with pros/cons.
            6. DO NOT summarize the conversation history ("User A said X").
            7. Use Markdown formatting (Bold, Bullet Points) for readability.
            8. Be helpful and detailed, providing concrete value.
            """

            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=f"Here is the chat log:\n\n{context_text}")]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, # Add system instruction here
                    temperature=0.7 # Slight creativity for planning
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

    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'username': event.get('username', 'System'),
                'system': event.get('system', False),
            }))
        except Exception:
            pass