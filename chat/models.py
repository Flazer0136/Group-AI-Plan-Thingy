# chat/models.py
from django.db import models

class Message(models.Model):
    room = models.CharField(max_length=50)
    # Use string reference to the user model to avoid get_user_model() at import time
    author = models.ForeignKey(
        'auth.User',              # or settings.AUTH_USER_MODEL if you add the import later
        on_delete=models.CASCADE,
        related_name='messages',
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'[{self.room}] {self.author.username}: {self.content[:20]}'


class AITokenUsage(models.Model):
    room = models.CharField(max_length=50)
    prompt_tokens = models.IntegerField()
    response_tokens = models.IntegerField()
    total_tokens = models.IntegerField()
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.room} - {self.total_tokens} tokens (${self.cost_usd})"