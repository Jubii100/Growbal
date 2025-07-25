from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import ChatSession, ChatMessage
from .serializers import (
    ChatSessionSerializer, ChatSessionCreateSerializer,
    ChatMessageSerializer, ChatMessageCreateSerializer,
    ChatHistorySerializer 
)
import uuid


class ChatSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chat sessions"""
    
    queryset = ChatSession.objects.all()
    permission_classes = [permissions.IsAuthenticated]  # require token auth
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ChatSessionCreateSerializer
        elif self.action == 'history':
            return ChatHistorySerializer
        return ChatSessionSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # If user is authenticated, show their sessions
        if self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(user=self.request.user) | Q(user__isnull=True)
            )
        
        # Filter by query parameters
        country = self.request.query_params.get('country')
        service_type = self.request.query_params.get('service_type')
        is_active = self.request.query_params.get('is_active')
        
        if country:
            queryset = queryset.filter(country=country)
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new chat session"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Optionally associate with authenticated user
        session_data = serializer.validated_data
        if request.user.is_authenticated:
            session_data['user'] = request.user
        
        session = ChatSession.objects.create(**session_data)
                
        # Return the created session
        output_serializer = ChatSessionSerializer(session)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get chat history in Gradio format"""
        session = self.get_object()
        serializer = self.get_serializer(session)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """End a chat session"""
        session = self.get_object()
        session.is_active = False
        session.save()
        
        # Update analytics
        if hasattr(session, 'analytics'):
            session.analytics.update_stats()
        
        return Response({'status': 'session ended'})
    
    @action(detail=False, methods=['get'])
    def by_session_id(self, request):
        """Get session by session_id (UUID)"""
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response(
                {'error': 'session_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session_uuid = uuid.UUID(session_id)
            session = get_object_or_404(ChatSession, session_id=session_uuid)
            serializer = ChatSessionSerializer(session)
            return Response(serializer.data)
        except ValueError:
            return Response(
                {'error': 'Invalid session_id format'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChatMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chat messages"""
    
    queryset = ChatMessage.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ChatMessageCreateSerializer
        return ChatMessageSerializer
    
    def get_queryset(self):
        """Filter messages by session"""
        queryset = super().get_queryset()
        
        # Filter by session_id if provided
        session_id = self.request.query_params.get('session_id')
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
                queryset = queryset.filter(session__session_id=session_uuid)
            except ValueError:
                pass
        
        # Filter by role if provided
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new chat message"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create the message
        message = serializer.save()
        
        # Update analytics if exists
        session = message.session
        if hasattr(session, 'analytics'):
            analytics = session.analytics
            analytics.total_messages += 1
            if message.role == 'user':
                analytics.user_messages += 1
            elif message.role == 'assistant':
                analytics.assistant_messages += 1
            analytics.save()
        
        # Return the created message
        output_serializer = ChatMessageSerializer(message)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple messages at once"""
        messages_data = request.data.get('messages', [])
        if not messages_data:
            return Response(
                {'error': 'messages field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_messages = []
        for msg_data in messages_data:
            serializer = ChatMessageCreateSerializer(data=msg_data)
            if serializer.is_valid():
                message = serializer.save()
                created_messages.append(message)
            else:
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Update analytics
        if created_messages:
            session = created_messages[0].session
            if hasattr(session, 'analytics'):
                session.analytics.update_stats()
        
        # Return created messages
        output_serializer = ChatMessageSerializer(created_messages, many=True)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get aggregated analytics summary"""
        queryset = self.get_queryset()
        
        from django.db.models import Sum, Avg, Count
        
        summary = queryset.aggregate(
            total_sessions=Count('id'),
            total_messages=Sum('total_messages'),
            avg_messages_per_session=Avg('total_messages'),
            total_user_messages=Sum('user_messages'),
            total_assistant_messages=Sum('assistant_messages'),
            avg_session_duration=Avg('session_duration')
        )
        
        # Get provider statistics
        all_providers = []
        for analytics in queryset:
            all_providers.extend(analytics.providers_found)
        
        provider_counts = {}
        for provider in all_providers:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        
        summary['top_providers'] = sorted(
            provider_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return Response(summary)
