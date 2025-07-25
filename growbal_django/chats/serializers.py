from rest_framework import serializers
from .models import ChatSession, ChatMessage
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model"""
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'session', 'role', 'content', 
            'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def to_representation(self, instance):
        """Custom representation for Gradio compatibility"""
        data = super().to_representation(instance)
        # Add Gradio-compatible format
        data['gradio_format'] = instance.to_gradio_format()
        return data


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for ChatSession model"""
    
    messages = ChatMessageSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    service_type_display = serializers.CharField(
        source='get_service_type_display', 
        read_only=True
    )
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'session_id', 'user', 'user_email', 'country', 
            'service_type', 'service_type_display', 'is_active',
            'created_at', 'last_activity', 'messages', 'message_count'
        ]
        read_only_fields = ['session_id', 'created_at', 'last_activity']
    
    def get_message_count(self, obj):
        """Get the total number of messages in the session"""
        return obj.messages.count()


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new chat session"""
    
    class Meta:
        model = ChatSession
        fields = ['country', 'service_type', 'user']
        
    def validate_service_type(self, value):
        """Validate service type matches the Gradio app options"""
        valid_choices = [choice[0] for choice in ChatSession.SERVICE_TYPE_CHOICES]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Invalid service type. Must be one of: {valid_choices}"
            )
        
        return value


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new chat messages"""
    
    session_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = ChatMessage
        fields = ['session_id', 'role', 'content', 'metadata']
        
    def validate_session_id(self, value):
        """Validate that the session exists"""
        try:
            session = ChatSession.objects.get(session_id=value)
            self.context['session'] = session
            return value
        except ChatSession.DoesNotExist:
            raise serializers.ValidationError("Invalid session ID")
    
    def create(self, validated_data):
        """Create the message and update session activity"""
        session_id = validated_data.pop('session_id')
        session = self.context['session']
        
        # Create the message
        message = ChatMessage.objects.create(
            session=session,
            **validated_data
        )
        
        # Update session last activity
        session.update_activity()
        
        return message


class ChatHistorySerializer(serializers.ModelSerializer):
    """Serializer for retrieving chat history in Gradio format"""
    
    messages = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = ['session_id', 'country', 'service_type', 'messages']
    
    def get_messages(self, obj):
        """Get messages in Gradio chat history format"""
        messages = obj.messages.all().order_by('created_at')
        history = []
        
        for msg in messages:
            if msg.role == 'user':
                # Find the next assistant message
                next_msg = messages.filter(
                    created_at__gt=msg.created_at,
                    role='assistant'
                ).first()
                
                if next_msg:
                    history.append([msg.content, next_msg.content])
        
        return history