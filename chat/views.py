import matplotlib
matplotlib.use('Agg') # Required for Django to run Matplotlib in background
import matplotlib.pyplot as plt
import io
import base64
import random
import string
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Message, RoomVisit, AITokenUsage

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
    recent_rooms = RoomVisit.objects.filter(user=request.user)[:5]
    return render(request, 'chat/room.html', {
        'room_name': room_name,
        'username': request.user.get_username(),
        'messages': messages,
        'recent_rooms': recent_rooms,
    })

@login_required
def delete_room(request, room_name):
    # Delete all data for this room
    Message.objects.filter(room=room_name).delete()
    RoomVisit.objects.filter(room=room_name).delete()
    AITokenUsage.objects.filter(room=room_name).delete()
    
    return redirect('chat:index')

@login_required
def get_room_stats(request, room_name):
    # 1. Fetch Data
    usage_data = AITokenUsage.objects.filter(room=room_name).order_by('timestamp')
    
    if not usage_data.exists():
        return JsonResponse({'status': 'no_data'})

    # 2. Prepare Data for Plotting
    # We'll plot Cumulative Cost over time
    timestamps = [u.timestamp for u in usage_data]
    costs = [float(u.cost_usd) for u in usage_data]
    
    # Calculate cumulative sum for a "Burn Rate" chart
    cumulative_cost = []
    current_sum = 0
    for c in costs:
        current_sum += c
        cumulative_cost.append(current_sum)

    # 3. Create Brutalist Plot
    plt.figure(figsize=(7, 4), facecolor='white')
    ax = plt.gca()
    ax.set_facecolor('white')
    
    # Plot Line
    plt.plot(timestamps, cumulative_cost, color='black', linewidth=2.5, drawstyle='steps-post')
    plt.fill_between(timestamps, cumulative_cost, color='black', alpha=0.1)
    
    # Styling (Monospace fonts, thick spines)
    plt.title(f"TOKEN BURN RATE: {room_name}", fontsize=10, fontweight='bold', fontname='monospace', pad=15)
    plt.ylabel("TOTAL COST ($)", fontsize=8, fontname='monospace')
    plt.grid(True, linestyle=':', linewidth=1, color='black', alpha=0.2)
    
    # Brutalist Spines
    for spine in ax.spines.values():
        spine.set_linewidth(2)
        spine.set_color('black')

    plt.xticks(fontsize=7, fontname='monospace', rotation=20)
    plt.yticks(fontsize=7, fontname='monospace')
    plt.tight_layout()
    
    # 4. Save to Base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    plt.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    
    return JsonResponse({
        'status': 'success',
        'chart': f"data:image/png;base64,{graphic}",
        'total_spent': round(current_sum, 4)
    })