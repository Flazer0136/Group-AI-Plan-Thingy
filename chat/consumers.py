import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        # 1. Determine Username
        user = self.scope.get('user')
        if user and user.is_authenticated:
            self.username = user.username
        else:
            # You can append a random ID here if you want unique colors for guests
            # e.g., f"Someone-{self.channel_name[-4:]}"
            self.username = "Someone"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"WebSocket connected: {self.channel_name}")
        
        # 2. Use actual name in join message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': f'👋 {self.username} joined the chat!',
                'username': 'System', # System messages don't need user colors
                'system': True
            }
        )

    async def disconnect(self, close_code):
        # 3. Use actual name in leave message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': f'👋 {self.username} left the chat',
                'username': 'System',
                'system': True
            }
        )
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        print(f"WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        
        print(f"Received message: {message}")
        
        # 4. Pass the specific username to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': self.username, # <--- SENDING USERNAME HERE
                'system': False
            }
        )

    async def chat_message(self, event):
        message = event['message']
        username = event.get('username', 'Unknown')
        is_system = event.get('system', False)
        
        # 5. Send data to frontend
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,
            'system': is_system
        }))