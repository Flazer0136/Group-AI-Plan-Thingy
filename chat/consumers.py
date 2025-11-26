import json
from channels.generic.websocket import WebsocketConsumer


class ChatConsumer(WebsocketConsumer):
    def connect(self):
        # Called when WebSocket connection is opened
        self.accept()
        print("WebSocket connected!")

    def disconnect(self, close_code):
        # Called when WebSocket connection is closed
        print(f"WebSocket disconnected with code: {close_code}")

    def receive(self, text_data):
        # Called when we receive a message from the client
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        
        print(f"Received message: {message}")
        
        # Echo the message back to the client
        self.send(text_data=json.dumps({
            'message': message
        }))
