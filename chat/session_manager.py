"""
Session Manager for FastAPI Chat Application
Provides fast database-backed session management with duplicate prevention
"""

import os
import sys
import uuid
from typing import Dict, Any, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from asgiref.sync import sync_to_async

# Add Django project to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
django_root = os.path.join(project_root, 'growbal_django')
sys.path.insert(0, project_root)
sys.path.insert(0, django_root)

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'growbal.settings')
import django
django.setup()

from chats.models import ChatSession, ChatMessage


class SessionManager:
    """Database-backed session manager with fast retrieval and duplicate prevention"""
    
    @staticmethod
    @sync_to_async
    def get_or_create_session(
        session_id: Optional[str] = None,
        country: Optional[str] = None,
        service_type: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[str, Dict[str, Any], bool]:
        """
        Get existing session or create new one with duplicate prevention.
        
        Args:
            session_id: Existing session ID to retrieve
            country: Country for new/existing session
            service_type: Service type for new/existing session
            user_id: Optional user ID
            
        Returns:
            Tuple of (session_id, session_data, is_new)
        """
        with transaction.atomic():
            # If session_id provided, try to retrieve it
            if session_id:
                try:
                    session = ChatSession.objects.select_for_update().get(
                        session_id=session_id
                    )
                    
                    # Verify country and service_type match if provided
                    if country and session.country != country:
                        # Mismatch - need new session
                        session_id = None
                    elif service_type and session.service_type != service_type:
                        # Mismatch - need new session
                        session_id = None
                    else:
                        # Valid existing session - update activity
                        session.update_activity()
                        return str(session.session_id), {
                            "country": session.country,
                            "service_type": session.service_type,
                            "created_at": session.created_at.timestamp(),
                            "active": session.is_active,
                            "last_activity": session.last_activity.timestamp(),
                            "user_id": session.user_id
                        }, False
                        
                except ChatSession.DoesNotExist:
                    # Invalid session ID - will create new one
                    session_id = None
            
            # Check for existing session with same country/service_type/user
            if country and service_type:
                # Look for recent active session with same parameters
                existing_session = ChatSession.objects.filter(
                    country=country,
                    service_type=service_type,
                    user_id=user_id,
                    is_active=True,
                    last_activity__gte=timezone.now() - timezone.timedelta(hours=24)
                ).order_by('-last_activity').first()
                
                if existing_session:
                    # Reuse existing session
                    existing_session.update_activity()
                    return str(existing_session.session_id), {
                        "country": existing_session.country,
                        "service_type": existing_session.service_type,
                        "created_at": existing_session.created_at.timestamp(),
                        "active": existing_session.is_active,
                        "last_activity": existing_session.last_activity.timestamp(),
                        "user_id": existing_session.user_id
                    }, False
            
            # Create new session
            new_session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(
                session_id=new_session_id,
                country=country or "unknown",
                service_type=service_type or "unknown",
                user_id=user_id,
                is_active=True
            )
            
            return str(session.session_id), {
                "country": session.country,
                "service_type": session.service_type,
                "created_at": session.created_at.timestamp(),
                "active": session.is_active,
                "last_activity": session.last_activity.timestamp(),
                "user_id": session.user_id
            }, True
    
    @staticmethod
    @sync_to_async
    def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session data dict or None if not found
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            return {
                "country": session.country,
                "service_type": session.service_type,
                "created_at": session.created_at.timestamp(),
                "active": session.is_active,
                "last_activity": session.last_activity.timestamp(),
                "user_id": session.user_id
            }
        except ChatSession.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def update_activity(session_id: str) -> bool:
        """
        Update session last activity timestamp.
        
        Args:
            session_id: Session ID to update
            
        Returns:
            True if updated, False if session not found
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            session.update_activity()
            return True
        except ChatSession.DoesNotExist:
            return False
    
    @staticmethod
    @sync_to_async
    def add_message(
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Add a message to the session.
        
        Args:
            session_id: Session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata dict
            
        Returns:
            Message ID if created, None if session not found
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            message = ChatMessage.objects.create(
                session=session,
                role=role,
                content=content,
                metadata=metadata or {}
            )
            session.update_activity()
            return message.id
        except ChatSession.DoesNotExist:
            return None
    
    @staticmethod
    @sync_to_async
    def get_session_history(session_id: str, limit: int = 10) -> list:
        """
        Get message history for a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            
        Returns:
            List of message dicts
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            messages = session.messages.order_by('-created_at')[:limit]
            
            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.metadata,
                    "created_at": msg.created_at.timestamp()
                }
                for msg in reversed(messages)
            ]
        except ChatSession.DoesNotExist:
            return []
    
    @staticmethod
    @sync_to_async
    def get_active_sessions_count() -> int:
        """Get count of active sessions."""
        return ChatSession.objects.filter(is_active=True).count()
    
    @staticmethod
    @sync_to_async
    def deactivate_old_sessions(hours: int = 24) -> int:
        """
        Deactivate sessions older than specified hours.
        
        Args:
            hours: Number of hours of inactivity before deactivation
            
        Returns:
            Number of sessions deactivated
        """
        cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
        return ChatSession.objects.filter(
            is_active=True,
            last_activity__lt=cutoff_time
        ).update(is_active=False)


# Create global instance
session_manager = SessionManager()