from django.shortcuts import render, redirect
import random
import string
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request, 'chat/index.html')

def create_room(request):
    # Generate random 6-character room code
    room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return redirect('chat:room', room_name=room_code)

@login_required
def room(request, room_name):
    return render(request, 'chat/room.html', {
        'room_name': room_name,
        'username': request.user.get_username(),  # or get_full_name()
    })
