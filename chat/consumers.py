import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': '👋 Someone joined the chat!',
                'username': 'System',
                'system': True,
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': '👋 Someone left the chat',
                'username': 'System',
                'system': True,
            }
        )
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

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
        # Get all messages from the room
        messages = await self.get_room_messages()
        
        # Generate AI response
        ai_response = await self.generate_ai_response(messages)
        
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
    
    async def generate_ai_response(self, messages):
        # Import here to avoid Python 3.14 compatibility issues
        from google.genai import types
        from google import genai
        
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            
            # Format chat history for Gemini
            conversation = "\n".join([
                f"{msg['author__username']}: {msg['content']}" 
                for msg in messages
            ])
            
            prompt = f"You are a helpful AI assistant in a chat room. Here's the conversation:\n\n{conversation}\n\nPlease provide a helpful response."
            
            gemini_messages = [
                types.Content(role="user", parts=[types.Part(text=prompt)])
            ]
            
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=gemini_messages
            )
            
            return response.text
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event.get('username', 'System'),
            'system': event.get('system', False),
        }))
