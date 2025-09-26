"""
Session Manager for FastAPI Chat Application
Provides fast database-backed session management with duplicate prevention
"""

import os
import sys
import uuid
import json
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
                print(f"Attempting to retrieve session with ID: {session_id}")
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
                            "user_id": session.auth_user_id,
                            "title": session.title
                        }, False
                        
                except ChatSession.DoesNotExist:
                    # Invalid session ID - will create new one
                    session_id = None
            
            # Create new session
            new_session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(
                session_id=new_session_id,
                country=country or "unknown",
                service_type=service_type or "unknown",
                auth_user_id=user_id,
                is_authenticated=bool(user_id),
                authentication_method='form' if user_id else 'anonymous',
                is_active=True
            )
            
            return str(session.session_id), {
                "country": session.country,
                "service_type": session.service_type,
                "created_at": session.created_at.timestamp(),
                "active": session.is_active,
                "last_activity": session.last_activity.timestamp(),
                "user_id": session.auth_user_id,
                "title": session.title
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
                "session_id": session.session_id,
                "country": session.country,
                "service_type": session.service_type,
                "created_at": session.created_at.timestamp(),
                "active": session.is_active,
                "last_activity": session.last_activity.timestamp(),
                "user_id": session.auth_user_id,
                "title": session.title
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
            
            # DEBUG: Write history to file for testing
            SessionManager._write_history_debug_file(session_id)
            
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
    def get_session_history_gradio(session_id: str, limit: int = 50) -> list:
        """
        Get message history for a session in Gradio format.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            
        Returns:
            List of message dicts in Gradio format
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            messages = session.messages.order_by('created_at')[:limit]
            
            # Convert to Gradio format (list of dicts with role and content)
            gradio_history = []
            for msg in messages:
                gradio_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            return gradio_history
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
    
    @staticmethod
    @sync_to_async
    def associate_session_with_user(session_id: str, user_id: int, auth_method: str = "form") -> bool:
        """
        Associate an existing session with an authenticated user
        
        Args:
            session_id: Session ID to update
            user_id: Authenticated user ID from MySQL
            auth_method: Authentication method used
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            session.auth_user_id = user_id
            session.is_authenticated = True
            session.authentication_method = auth_method
            session.save(update_fields=['auth_user_id', 'is_authenticated', 'authentication_method'])
            
            return True
        except ChatSession.DoesNotExist:
            return False

    @staticmethod
    @sync_to_async
    def get_user_sessions(user_id: int, active_only: bool = True) -> list:
        """
        Get all sessions for a specific authenticated user
        
        Args:
            user_id: User ID to search for
            active_only: Whether to return only active sessions
            
        Returns:
            List of session dictionaries
        """
        try:
            sessions_query = ChatSession.objects.filter(auth_user_id=user_id)
            
            if active_only:
                sessions_query = sessions_query.filter(is_active=True)
            
            sessions = sessions_query.order_by('-last_activity')
            
            return [
                {
                    "session_id": session.session_id,
                    "country": session.country,
                    "service_type": session.service_type,
                    "created_at": session.created_at.timestamp(),
                    "last_activity": session.last_activity.timestamp(),
                    "is_active": session.is_active,
                    "authentication_method": session.authentication_method,
                    "title": session.title or f"{session.get_service_type_display()} - {session.country}"
                }
                for session in sessions
            ]
        except Exception as e:
            print(f"Error retrieving user sessions: {e}")
            return []
    
    @staticmethod
    @sync_to_async
    def update_session_title(session_id: str, title: str) -> bool:
        """
        Update the title of a session.
        
        Args:
            session_id: Session ID to update
            title: New title for the session
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            session.title = title[:200]  # Ensure it fits in the field
            session.save(update_fields=['title'])
            return True
        except ChatSession.DoesNotExist:
            return False
    
    @staticmethod
    def _write_history_debug_file(session_id: str):
        """
        DEBUG: Write session history to a text file for testing
        """
        try:
            session = ChatSession.objects.get(session_id=session_id)
            messages = session.messages.order_by('created_at')
            
            debug_file_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                'session_history_debug.txt'
            )
            
            with open(debug_file_path, 'w', encoding='utf-8') as f:
                f.write(f"=== SESSION HISTORY DEBUG ===\n")
                f.write(f"Session ID: {session_id}\n")
                f.write(f"Country: {session.country}\n")
                f.write(f"Service Type: {session.service_type}\n")
                f.write(f"Created: {session.created_at}\n")
                f.write(f"Last Activity: {session.last_activity}\n")
                f.write(f"Total Messages: {messages.count()}\n")
                f.write(f"{'='*50}\n\n")
                
                for i, msg in enumerate(messages, 1):
                    f.write(f"Message #{i}\n")
                    f.write(f"Role: {msg.role.upper()}\n")
                    f.write(f"Time: {msg.created_at}\n")
                    f.write(f"Content: {msg.content}\n")
                    if msg.metadata:
                        f.write(f"Metadata: {msg.metadata}\n")
                    f.write(f"{'-'*30}\n\n")
                
                f.write(f"\n=== GRADIO FORMAT HISTORY ===\n")
                gradio_history = []
                for msg in messages:
                    gradio_history.append({
                        "role": msg.role,
                        "content": msg.content
                    })
                f.write(f"{json.dumps(gradio_history, indent=2)}\n")
                
                f.write(f"\n=== END OF HISTORY ===\n")
                f.write(f"File updated at: {timezone.now()}\n")
                
        except Exception as e:
            # Don't fail the main operation if debug writing fails
            print(f"Debug file write error: {e}")


# Create global instance
session_manager = SessionManager()