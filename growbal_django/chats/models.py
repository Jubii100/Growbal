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


class ChatAnalytics(models.Model):
    """Model to store analytics and aggregated data for chat sessions"""
    
    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='analytics',
        help_text="Chat session these analytics belong to"
    )
    total_messages = models.PositiveIntegerField(
        default=0,
        help_text="Total number of messages in the session"
    )
    user_messages = models.PositiveIntegerField(
        default=0,
        help_text="Number of user messages"
    )
    assistant_messages = models.PositiveIntegerField(
        default=0,
        help_text="Number of assistant messages"
    )
    providers_found = models.JSONField(
        default=list,
        blank=True,
        help_text="List of service providers found during the session"
    )
    search_queries = models.JSONField(
        default=list,
        blank=True,
        help_text="Search queries performed during the session"
    )
    session_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Duration of the chat session"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update to analytics"
    )
    
    class Meta:
        verbose_name = "Chat Analytics"
        verbose_name_plural = "Chat Analytics"
    
    def __str__(self):
        return f"Analytics for {self.session.session_id}"
    
    def update_stats(self):
        """Update analytics statistics"""
        messages = self.session.messages.all()
        self.total_messages = messages.count()
        self.user_messages = messages.filter(role='user').count()
        self.assistant_messages = messages.filter(role='assistant').count()
        
        if self.session.is_active:
            self.session_duration = timezone.now() - self.session.created_at
        
        self.save()
