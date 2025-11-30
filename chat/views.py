from django.shortcuts import render, redirect
import random
import string
from django.contrib.auth.decorators import login_required
from .models import Message, RoomVisit 

@login_required
def index(request):
    recent_rooms = RoomVisit.objects.filter(user=request.user)[:5]
    return render(request, 'chat/index.html', {
        'recent_rooms': recent_rooms
    })


def create_room(request):
    # Generate random 6-character room code
    room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return redirect('chat:room', room_name=room_code)


@login_required
def room(request, room_name):
    messages = Message.objects.filter(room=room_name).select_related('author')[:50]
    return render(request, 'chat/room.html', {
        'room_name': room_name,
        'username': request.user.get_username(),
        'messages': messages,
    })
