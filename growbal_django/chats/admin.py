from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import ChatSession, ChatMessage


class ChatMessageInline(admin.TabularInline):
    """Inline admin for chat messages within a session"""
    model = ChatMessage
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('role', 'content', 'metadata', 'created_at')
    ordering = ('created_at',)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of messages to maintain history integrity"""
        return False

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """Admin interface for ChatSession model"""
    
    list_display = (
        'session_id_short', 'user_link', 'country', 'service_type_display',
        'is_active', 'message_count', 'duration', 'created_at', 'last_activity'
    )
    list_filter = (
        'is_active', 'service_type', 'country', 
        'created_at', 'last_activity'
    )
    search_fields = (
        'session_id', 'user__email', 'user__username', 
        'country', 'messages__content'
    )
    readonly_fields = (
        'session_id', 'created_at', 'last_activity',
        'message_count', 'duration', 'chat_preview'
    )
    fieldsets = (
        ('Session Information', {
            'fields': ('session_id', 'user', 'country', 'service_type', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_activity', 'duration')
        }),
        ('Statistics', {
            'fields': ('message_count', 'chat_preview')
        })
    )
    inlines = [ChatMessageInline]
    date_hierarchy = 'created_at'
    
    def session_id_short(self, obj):
        """Display shortened session ID"""
        return format_html(
            '<span title="{}">{}</span>',
            obj.session_id,
            str(obj.session_id)[:8] + '...'
        )
    session_id_short.short_description = 'Session ID'
    
    def user_link(self, obj):
        """Link to user admin page"""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_link.short_description = 'User'
    
    def service_type_display(self, obj):
        """Display service type"""
        return obj.get_service_type_display()
    service_type_display.short_description = 'Service Type'
    
    def message_count(self, obj):
        """Display total message count"""
        count = obj.messages.count()
        return format_html(
            '<span style="color: {};">{} messages</span>',
            '#28a745' if count > 0 else '#6c757d',
            count
        )
    message_count.short_description = 'Messages'
    
    def duration(self, obj):
        """Display session duration"""
        # Handle case where object hasn't been saved yet (add form)
        if obj.created_at is None:
            return "N/A"
            
        if obj.is_active:
            from django.utils import timezone
            duration = timezone.now() - obj.created_at
        else:
            # Handle case where last_activity might be None
            if obj.last_activity is None:
                return "N/A"
            duration = obj.last_activity - obj.created_at
        
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"
    duration.short_description = 'Duration'
    
    def chat_preview(self, obj):
        """Show preview of last few messages"""
        messages = obj.messages.order_by('-created_at')[:3]
        if not messages:
            return "No messages yet"
        
        preview_html = '<div style="max-width: 600px;">'
        for msg in reversed(messages):
            role_color = '#007bff' if msg.role == 'user' else '#28a745'
            preview_html += format_html(
                '<div style="margin: 5px 0; padding: 8px; background: #f8f9fa; '
                'border-left: 3px solid {}; border-radius: 3px;">'
                '<strong>{}</strong>: {}</div>',
                role_color,
                msg.get_role_display(),
                msg.content[:100] + '...' if len(msg.content) > 100 else msg.content
            )
        preview_html += '</div>'
        return format_html(preview_html)
    chat_preview.short_description = 'Recent Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for ChatMessage model"""
    
    list_display = (
        'id', 'session_link', 'role', 'content_preview', 
        'has_metadata', 'created_at'
    )
    list_filter = ('role', 'created_at', 'session__country', 'session__service_type')
    search_fields = ('content', 'session__session_id', 'metadata')
    readonly_fields = ('created_at', 'formatted_metadata')
    fieldsets = (
        ('Message Information', {
            'fields': ('session', 'role', 'content')
        }),
        ('Metadata', {
            'fields': ('metadata', 'formatted_metadata'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )
    date_hierarchy = 'created_at'
    
    def session_link(self, obj):
        """Link to session admin page"""
        url = reverse('admin:chats_chatsession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            str(obj.session.session_id)[:8] + '...'
        )
    session_link.short_description = 'Session'
    
    def content_preview(self, obj):
        """Preview of message content"""
        max_length = 100
        if len(obj.content) > max_length:
            return obj.content[:max_length] + '...'
        return obj.content
    content_preview.short_description = 'Content'
    
    def has_metadata(self, obj):
        """Check if message has metadata"""
        return bool(obj.metadata and obj.metadata != {})
    has_metadata.boolean = True
    has_metadata.short_description = 'Has Metadata'
    
    def formatted_metadata(self, obj):
        """Display formatted metadata"""
        if not obj.metadata:
            return "No metadata"
        
        import json
        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px; '
            'border-radius: 3px; overflow: auto;">{}</pre>',
            json.dumps(obj.metadata, indent=2)
        )
    formatted_metadata.short_description = 'Formatted Metadata'

    def session_link(self, obj):
        """Link to session admin page"""
        url = reverse('admin:chats_chatsession_change', args=[obj.session.pk])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            str(obj.session.session_id)[:8] + '...'
        )
    session_link.short_description = 'Session'
    
    def provider_count(self, obj):
        """Count of providers found"""
        return len(obj.providers_found)
    provider_count.short_description = 'Providers Found'
    
    def formatted_providers(self, obj):
        """Display formatted provider list"""
        if not obj.providers_found:
            return "No providers found"
        
        html = '<ul style="margin: 0; padding-left: 20px;">'
        for provider in obj.providers_found:
            html += f'<li>{provider}</li>'
        html += '</ul>'
        return format_html(html)
    formatted_providers.short_description = 'Providers Found'
    
    def formatted_queries(self, obj):
        """Display formatted search queries"""
        if not obj.search_queries:
            return "No search queries"
        
        html = '<ol style="margin: 0; padding-left: 20px;">'
        for query in obj.search_queries:
            html += f'<li>{query}</li>'
        html += '</ol>'
        return format_html(html)
    formatted_queries.short_description = 'Search Queries'
    
    def has_add_permission(self, request):
        """Prevent manual creation of analytics"""
        return False
