from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class ChatSession(models.Model):
    """Model to store chat session metadata"""
    
    SERVICE_TYPE_CHOICES = [
        ('Tax Services', 'Tax Services'),
        ('Business Setup Services', 'Business Setup Services'),
        ('Migration/Visa Services', 'Migration/Visa Services'),
    ]
    
    session_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the chat session"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
        null=True,
        blank=True,
        help_text="User associated with this chat session (optional)"
    )
    country = models.CharField(
        max_length=100,
        help_text="Country selected for service search"
    )
    service_type = models.CharField(
        max_length=50,
        choices=SERVICE_TYPE_CHOICES,
        help_text="Type of service being searched"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the session is currently active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the session was created"
    )
    last_activity = models.DateTimeField(
        default=timezone.now,
        help_text="Last activity timestamp"
    )
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['country', 'service_type']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-last_activity']),
        ]
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"
    
    def __str__(self):
        return f"Session {self.session_id} - {self.country} - {self.get_service_type_display()}"
    
    def update_activity(self):
        """Update the last activity timestamp"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])


class ChatMessage(models.Model):
    """Model to store individual chat messages"""
    
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="Chat session this message belongs to"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="Role of the message sender"
    )
    content = models.TextField(
        help_text="Message content"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (thinking blocks, search results, etc.)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the message was created"
    )
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['role']),
        ]
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}..."
    
    def to_gradio_format(self):
        """Convert to Gradio chat interface format"""
        return {
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata
        }