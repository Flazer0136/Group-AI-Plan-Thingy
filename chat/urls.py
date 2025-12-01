from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_room, name='create_room'),
    
    # API Routes
    path('api/stats/<str:room_name>/', views.get_room_stats, name='room_stats'),
    
    # Room Routes
    path('<str:room_name>/', views.room, name='room'),
    path('<str:room_name>/delete/', views.delete_room, name='delete_room'),
]