# Phase 4: Session Management Integration

## Overview

This phase integrates authentication with the existing Django-based session management system. We'll enhance the current ChatSession model to support authenticated users while maintaining backward compatibility with anonymous sessions.

## Prerequisites

- Phase 1 (Database Setup) completed
- Phase 2 (Password Verification) completed  
- Phase 3 (Login System) completed
- Existing Django ChatSession model and session_manager.py

## 1. Enhanced Session Management

### Update ChatSession Model

First, let's extend the existing ChatSession model. Add these fields to `growbal_django/chats/models.py`:

```python
# Add to the imports at the top
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

# Add these fields to the ChatSession model (after existing fields)

    # Authentication-related fields
    auth_user_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="External MySQL authentication user ID",
        db_index=True
    )
    auth_username = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        help_text="Username from authentication system",
        db_index=True
    )
    is_authenticated = models.BooleanField(
        default=False,
        help_text="Whether this session belongs to an authenticated user",
        db_index=True
    )
    authentication_method = models.CharField(
        max_length=20,
        choices=[
            ('anonymous', 'Anonymous'),
            ('form', 'Form Login'),
            ('sso', 'Single Sign-On'),
        ],
        default='anonymous',
        help_text="Method used for authentication"
    )
    session_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Session token for additional security",
        db_index=True
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Session expiration timestamp"
    )
    
    # Add to the Meta class indexes
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['country', 'service_type']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-last_activity']),
            models.Index(fields=['auth_user_id', '-created_at']),  # New
            models.Index(fields=['is_authenticated', '-last_activity']),  # New
            models.Index(fields=['session_token']),  # New
        ]
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"
    
    # Add new methods
    def is_expired(self):
        """Check if session has expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def extend_session(self, hours: int = 8):
        """Extend session expiration"""
        self.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        self.save(update_fields=['expires_at'])
    
    def invalidate_session(self):
        """Invalidate the session"""
        self.is_active = False
        self.expires_at = timezone.now()
        self.save(update_fields=['is_active', 'expires_at'])
    
    def get_auth_context(self):
        """Get authentication context for this session"""
        return {
            'is_authenticated': self.is_authenticated,
            'auth_user_id': self.auth_user_id,
            'auth_username': self.auth_username,
            'authentication_method': self.authentication_method,
            'expires_at': self.expires_at,
            'is_expired': self.is_expired()
        }
```

### Create and Run Migration

```bash
cd growbal_django
python manage.py makemigrations chats
python manage.py migrate
```

## 2. Enhanced Session Manager

### Update session_manager.py

Add these enhanced methods to your existing `session_manager.py`:

```python
import secrets
from datetime import datetime, timedelta
from django.utils import timezone

class SessionManager:
    # ... existing methods ...
    
    @staticmethod
    @sync_to_async
    def create_authenticated_session(
        user_id: int,
        username: str,
        country: str,
        service_type: str,
        auth_method: str = "form",
        remember_me: bool = False
    ) -> Tuple[str, Dict[str, Any], bool]:
        """
        Create a new authenticated session
        
        Args:
            user_id: Authenticated user ID from MySQL
            username: Username from authentication
            country: Country for session
            service_type: Service type for session
            auth_method: Authentication method used
            remember_me: Whether to create long-lived session
            
        Returns:
            Tuple of (session_id, session_data, is_new)
        """
        with transaction.atomic():
            # Generate session token for additional security
            session_token = secrets.token_urlsafe(32)
            
            # Set expiration based on remember_me
            if remember_me:
                expires_at = timezone.now() + timedelta(days=30)
            else:
                expires_at = timezone.now() + timedelta(hours=8)
            
            # Create new session
            new_session_id = str(uuid.uuid4())
            session = ChatSession.objects.create(
                session_id=new_session_id,
                country=country,
                service_type=service_type,
                user_id=None,  # Keep existing Django user field empty
                auth_user_id=user_id,
                auth_username=username,
                is_authenticated=True,
                authentication_method=auth_method,
                session_token=session_token,
                expires_at=expires_at,
                is_active=True
            )
            
            print(f"✅ Created authenticated session {new_session_id} for user {username}")
            
            return str(session.session_id), {
                "session_id": session.session_id,
                "country": session.country,
                "service_type": session.service_type,
                "created_at": session.created_at.timestamp(),
                "active": session.is_active,
                "last_activity": session.last_activity.timestamp(),
                "auth_user_id": session.auth_user_id,
                "auth_username": session.auth_username,
                "is_authenticated": session.is_authenticated,
                "authentication_method": session.authentication_method,
                "session_token": session_token,
                "expires_at": session.expires_at.timestamp()
            }, True
    
    @staticmethod
    @sync_to_async
    def validate_authenticated_session(
        session_id: str,
        session_token: str = None,
        user_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validate an authenticated session with additional security checks
        
        Args:
            session_id: Session ID to validate
            session_token: Optional session token for additional security
            user_id: Optional user ID to match
            
        Returns:
            Session data dict or None if invalid
        """
        try:
            session = ChatSession.objects.get(
                session_id=session_id,
                is_active=True,
                is_authenticated=True
            )
            
            # Check expiration
            if session.is_expired():
                print(f"🕒 Session {session_id} has expired")
                session.invalidate_session()
                return None
            
            # Check session token if provided
            if session_token and session.session_token != session_token:
                print(f"🔒 Session token mismatch for {session_id}")
                return None
            
            # Check user ID if provided
            if user_id and session.auth_user_id != user_id:
                print(f"👤 User ID mismatch for session {session_id}")
                return None
            
            # Update activity
            session.update_activity()
            
            return {
                "session_id": session.session_id,
                "country": session.country,
                "service_type": session.service_type,
                "created_at": session.created_at.timestamp(),
                "active": session.is_active,
                "last_activity": session.last_activity.timestamp(),
                "auth_user_id": session.auth_user_id,
                "auth_username": session.auth_username,
                "is_authenticated": session.is_authenticated,
                "authentication_method": session.authentication_method,
                "expires_at": session.expires_at.timestamp() if session.expires_at else None
            }
            
        except ChatSession.DoesNotExist:
            print(f"❌ Session {session_id} not found")
            return None
    
    @staticmethod
    @sync_to_async
    def associate_session_with_user(
        session_id: str,
        user_id: int,
        username: str,
        auth_method: str = "form"
    ) -> bool:
        """
        Associate an existing anonymous session with an authenticated user
        
        Args:
            session_id: Existing session ID
            user_id: Authenticated user ID
            username: Username
            auth_method: Authentication method
            
        Returns:
            True if updated successfully
        """
        try:
            with transaction.atomic():
                session = ChatSession.objects.select_for_update().get(
                    session_id=session_id
                )
                
                # Generate session token
                session_token = secrets.token_urlsafe(32)
                
                # Update session with authentication info
                session.auth_user_id = user_id
                session.auth_username = username
                session.is_authenticated = True
                session.authentication_method = auth_method
                session.session_token = session_token
                session.expires_at = timezone.now() + timedelta(hours=8)
                session.save(update_fields=[
                    'auth_user_id', 'auth_username', 'is_authenticated',
                    'authentication_method', 'session_token', 'expires_at'
                ])
                
                print(f"✅ Associated session {session_id} with user {username}")
                return True
                
        except ChatSession.DoesNotExist:
            print(f"❌ Session {session_id} not found for association")
            return False
    
    @staticmethod
    @sync_to_async
    def get_user_sessions(
        user_id: int,
        active_only: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all sessions for a specific user
        
        Args:
            user_id: User ID to search for
            active_only: Whether to return only active sessions
            limit: Maximum number of sessions to return
            
        Returns:
            List of session dictionaries
        """
        try:
            sessions_query = ChatSession.objects.filter(
                auth_user_id=user_id,
                is_authenticated=True
            )
            
            if active_only:
                sessions_query = sessions_query.filter(
                    is_active=True
                ).exclude(
                    expires_at__lt=timezone.now()
                )
            
            sessions = sessions_query.order_by('-last_activity')[:limit]
            
            return [
                {
                    "session_id": str(session.session_id),
                    "country": session.country,
                    "service_type": session.service_type,
                    "created_at": session.created_at.timestamp(),
                    "last_activity": session.last_activity.timestamp(),
                    "is_active": session.is_active,
                    "authentication_method": session.authentication_method,
                    "expires_at": session.expires_at.timestamp() if session.expires_at else None,
                    "is_expired": session.is_expired(),
                    "message_count": session.messages.count()
                }
                for session in sessions
            ]
            
        except Exception as e:
            print(f"❌ Error retrieving user sessions: {e}")
            return []
    
    @staticmethod
    @sync_to_async
    def extend_session_expiration(
        session_id: str,
        hours: int = 8
    ) -> bool:
        """
        Extend session expiration
        
        Args:
            session_id: Session ID to extend
            hours: Number of hours to extend
            
        Returns:
            True if extended successfully
        """
        try:
            session = ChatSession.objects.get(
                session_id=session_id,
                is_active=True
            )
            
            session.extend_session(hours)
            print(f"⏰ Extended session {session_id} by {hours} hours")
            return True
            
        except ChatSession.DoesNotExist:
            print(f"❌ Session {session_id} not found for extension")
            return False
    
    @staticmethod
    @sync_to_async
    def invalidate_user_sessions(
        user_id: int,
        except_session_id: str = None
    ) -> int:
        """
        Invalidate all sessions for a user (useful for security)
        
        Args:
            user_id: User ID whose sessions to invalidate
            except_session_id: Optional session ID to keep active
            
        Returns:
            Number of sessions invalidated
        """
        try:
            sessions_query = ChatSession.objects.filter(
                auth_user_id=user_id,
                is_active=True
            )
            
            if except_session_id:
                sessions_query = sessions_query.exclude(session_id=except_session_id)
            
            count = sessions_query.update(
                is_active=False,
                expires_at=timezone.now()
            )
            
            print(f"🔒 Invalidated {count} sessions for user {user_id}")
            return count
            
        except Exception as e:
            print(f"❌ Error invalidating user sessions: {e}")
            return 0
    
    @staticmethod
    @sync_to_async
    def cleanup_expired_sessions() -> int:
        """
        Clean up expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            now = timezone.now()
            count = ChatSession.objects.filter(
                expires_at__lt=now,
                is_active=True
            ).update(is_active=False)
            
            print(f"🧹 Cleaned up {count} expired sessions")
            return count
            
        except Exception as e:
            print(f"❌ Error cleaning up expired sessions: {e}")
            return 0
    
    @staticmethod
    @sync_to_async
    def get_session_statistics() -> Dict[str, Any]:
        """
        Get session statistics for monitoring
        
        Returns:
            Dictionary with session statistics
        """
        try:
            now = timezone.now()
            
            stats = {
                "total_sessions": ChatSession.objects.count(),
                "active_sessions": ChatSession.objects.filter(is_active=True).count(),
                "authenticated_sessions": ChatSession.objects.filter(
                    is_authenticated=True,
                    is_active=True
                ).count(),
                "anonymous_sessions": ChatSession.objects.filter(
                    is_authenticated=False,
                    is_active=True
                ).count(),
                "expired_sessions": ChatSession.objects.filter(
                    expires_at__lt=now,
                    is_active=True
                ).count(),
                "sessions_last_24h": ChatSession.objects.filter(
                    created_at__gte=now - timedelta(days=1)
                ).count(),
                "active_users_today": ChatSession.objects.filter(
                    is_authenticated=True,
                    last_activity__gte=now - timedelta(days=1)
                ).values('auth_user_id').distinct().count()
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting session statistics: {e}")
            return {}
```

## 3. Integration with Authentication System

### Update Authentication Dependencies

Modify your `authentication/dependencies.py` to work with the enhanced session manager:

```python
from chat.session_manager import session_manager

async def get_current_user_from_session(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user from FastAPI session and validate with database
    """
    
    # Check FastAPI session
    if not request.session.get("authenticated"):
        return None
    
    session_id = request.session.get("chat_session_id")
    session_token = request.session.get("session_token")
    user_id = request.session.get("user_id")
    
    if not all([session_id, user_id]):
        # Clear invalid session
        request.session.clear()
        return None
    
    # Validate with database session
    session_data = await session_manager.validate_authenticated_session(
        session_id=session_id,
        session_token=session_token,
        user_id=user_id
    )
    
    if not session_data:
        # Session invalid in database, clear FastAPI session
        request.session.clear()
        return None
    
    # Update FastAPI session with fresh data
    request.session["last_validated"] = datetime.now().isoformat()
    
    return {
        "user_id": session_data["auth_user_id"],
        "username": session_data["auth_username"],
        "session_id": session_data["session_id"],
        "auth_method": session_data["authentication_method"],
        "expires_at": session_data.get("expires_at")
    }

async def require_authentication_with_session(request: Request) -> Dict[str, Any]:
    """
    Enhanced authentication dependency that integrates with session management
    """
    
    user = await get_current_user_from_session(request)
    if not user:
        # Store original URL for redirect after login
        original_url = str(request.url)
        if request.method == "GET" and not original_url.endswith("/login"):
            request.session["redirect_after_login"] = original_url
        
        # For API endpoints, return 401
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # For web pages, redirect to login
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    
    return user
```

## 4. Enhanced Login Process

### Update Login Handler

Modify your login handler in `main.py` to integrate with session management:

```python
@app.post("/login")
async def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: bool = Form(False)
):
    """Enhanced login handler with session management integration"""
    
    # ... existing validation code ...
    
    try:
        # Authenticate user
        auth_result = await auth_service.authenticate_user(login_request)
        
        if auth_result.success:
            # Clear failed attempts
            security_utils.clear_failed_attempts(client_ip)
            
            # Check if user has existing chat session to associate
            existing_session_id = request.session.get("session_id")
            chat_session_id = None
            session_token = None
            
            if existing_session_id:
                # Associate existing session with authenticated user
                success = await session_manager.associate_session_with_user(
                    session_id=existing_session_id,
                    user_id=auth_result.user.user_id,
                    username=auth_result.user.username,
                    auth_method="form"
                )
                
                if success:
                    chat_session_id = existing_session_id
                    # Get updated session data
                    session_data = await session_manager.get_session(existing_session_id)
                    session_token = session_data.get("session_token") if session_data else None
            
            # If no existing session, user will create one when they proceed to chat
            
            # Store authentication info in FastAPI session
            request.session["authenticated"] = True
            request.session["user_id"] = auth_result.user.user_id
            request.session["username"] = auth_result.user.username
            request.session["auth_method"] = "form"
            
            if chat_session_id:
                request.session["chat_session_id"] = chat_session_id
                request.session["session_token"] = session_token
            
            # Set session expiration
            if remember_me:
                request.session["session_expires"] = (
                    datetime.now() + timedelta(days=30)
                ).isoformat()
            else:
                request.session["session_expires"] = (
                    datetime.now() + timedelta(hours=8)
                ).isoformat()
            
            # Log successful login
            logger.info(f"Successful login: {username} from {client_ip}")
            
            # Redirect to original destination
            redirect_url = request.session.get("redirect_after_login", "/country/")
            request.session.pop("redirect_after_login", None)
            
            return RedirectResponse(url=redirect_url, status_code=HTTP_303_SEE_OTHER)
        
        # ... existing error handling ...
```

### Update Chat Session Creation

Modify your `/proceed-to-chat` endpoint to create authenticated sessions:

```python
@app.post("/proceed-to-chat")
async def proceed_to_chat(
    request: Request, 
    country: str = Form(...), 
    service_type: str = Form(...),
    current_user: Dict[str, Any] = Depends(require_authentication_with_session)
):
    """Enhanced chat session creation for authenticated users"""
    
    if not country or not service_type:
        raise HTTPException(status_code=400, detail="Country and service type are required")
    
    # Check if user already has a chat session
    existing_session_id = request.session.get("chat_session_id")
    
    if existing_session_id:
        # Validate existing session
        session_data = await session_manager.validate_authenticated_session(
            session_id=existing_session_id,
            user_id=current_user["user_id"]
        )
        
        if session_data and session_data["country"] == country and session_data["service_type"] == service_type:
            # Reuse existing session
            session_id = existing_session_id
            print(f"♻️ Reusing existing authenticated session: {session_id}")
        else:
            # Create new session
            session_id, session_data, is_new = await session_manager.create_authenticated_session(
                user_id=current_user["user_id"],
                username=current_user["username"],
                country=country,
                service_type=service_type,
                auth_method=current_user["auth_method"],
                remember_me=False  # Could be passed from form if needed
            )
            
            # Update FastAPI session
            request.session["chat_session_id"] = session_id
            request.session["session_token"] = session_data["session_token"]
            
            print(f"🆕 Created new authenticated session: {session_id}")
    else:
        # Create new session
        session_id, session_data, is_new = await session_manager.create_authenticated_session(
            user_id=current_user["user_id"],
            username=current_user["username"],
            country=country,
            service_type=service_type,
            auth_method=current_user["auth_method"],
            remember_me=False
        )
        
        # Update FastAPI session
        request.session["chat_session_id"] = session_id
        request.session["session_token"] = session_data["session_token"]
        
        print(f"🆕 Created new authenticated session: {session_id}")
    
    # Update other session data
    request.session["country"] = country
    request.session["service_type"] = service_type
    
    print(f"🚀 Redirecting to authenticated chat: User={current_user['username']}, Session={session_id}")
    
    # Redirect to chat interface
    redirect_url = f"/chat/?session_id={session_id}"
    return RedirectResponse(url=redirect_url, status_code=303)
```

## 5. User Dashboard and Session Management

### Create User Dashboard

Create `templates/dashboard.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Growbal Intelligence - Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', Arial, sans-serif;
            background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
            min-height: 100vh;
        }
        .dashboard-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(25, 132, 132, 0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .welcome-text {
            font-size: 1.5rem;
            font-weight: 700;
            color: #2b5556;
        }
        .user-actions {
            display: flex;
            gap: 15px;
        }
        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: linear-gradient(135deg, #198484 0%, #16a6a6 100%);
            color: white;
        }
        .btn-secondary {
            background: #f8f9fa;
            color: #2b5556;
            border: 1px solid #dee2e6;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(25, 132, 132, 0.1);
            text-align: center;
        }
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #198484;
            margin-bottom: 10px;
        }
        .stat-label {
            font-size: 1rem;
            color: #666;
        }
        .sessions-section {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(25, 132, 132, 0.1);
        }
        .section-title {
            font-size: 1.3rem;
            font-weight: 700;
            color: #2b5556;
            margin-bottom: 20px;
        }
        .session-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            border: 1px solid #f0f0f0;
            border-radius: 10px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .session-item:hover {
            border-color: #198484;
            box-shadow: 0 2px 10px rgba(25, 132, 132, 0.1);
        }
        .session-info {
            flex: 1;
        }
        .session-title {
            font-weight: 600;
            color: #2b5556;
            margin-bottom: 5px;
        }
        .session-meta {
            font-size: 0.9rem;
            color: #666;
        }
        .session-actions {
            display: flex;
            gap: 10px;
        }
        .btn-small {
            padding: 6px 12px;
            font-size: 0.8rem;
        }
        .no-sessions {
            text-align: center;
            padding: 40px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="header">
            <div class="welcome-text">
                Welcome back, {{ username }}!
            </div>
            <div class="user-actions">
                <a href="/country/" class="btn btn-primary">New Chat Session</a>
                <form method="post" action="/logout" style="display: inline;">
                    <button type="submit" class="btn btn-secondary">Logout</button>
                </form>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ stats.active_sessions or 0 }}</div>
                <div class="stat-label">Active Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_messages or 0 }}</div>
                <div class="stat-label">Total Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.countries_used or 0 }}</div>
                <div class="stat-label">Countries Explored</div>
            </div>
        </div>
        
        <div class="sessions-section">
            <h2 class="section-title">Your Recent Sessions</h2>
            
            {% if sessions %}
                {% for session in sessions %}
                <div class="session-item">
                    <div class="session-info">
                        <div class="session-title">
                            {{ session.country }} - {{ session.service_type }}
                        </div>
                        <div class="session-meta">
                            Created: {{ session.created_at_formatted }} | 
                            Last active: {{ session.last_activity_formatted }} |
                            Messages: {{ session.message_count }}
                        </div>
                    </div>
                    <div class="session-actions">
                        <a href="/chat/?session_id={{ session.session_id }}" class="btn btn-primary btn-small">
                            Continue
                        </a>
                        {% if not session.is_active %}
                        <span class="btn btn-secondary btn-small" style="opacity: 0.6;">
                            Expired
                        </span>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-sessions">
                    <p>No chat sessions yet. <a href="/country/">Start your first session!</a></p>
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
```

### Add Dashboard Route

Add this route to your main application:

```python
@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authentication_with_session)
):
    """User dashboard showing sessions and statistics"""
    
    # Get user sessions
    sessions = await session_manager.get_user_sessions(
        user_id=current_user["user_id"],
        active_only=False,
        limit=20
    )
    
    # Format session data for template
    formatted_sessions = []
    for session in sessions:
        formatted_sessions.append({
            **session,
            "created_at_formatted": datetime.fromtimestamp(session["created_at"]).strftime("%B %d, %Y at %I:%M %p"),
            "last_activity_formatted": datetime.fromtimestamp(session["last_activity"]).strftime("%B %d, %Y at %I:%M %p")
        })
    
    # Calculate user statistics
    stats = {
        "active_sessions": len([s for s in sessions if s["is_active"] and not s["is_expired"]]),
        "total_messages": sum(s["message_count"] for s in sessions),
        "countries_used": len(set(s["country"] for s in sessions))
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": current_user["username"],
        "sessions": formatted_sessions,
        "stats": stats
    })
```

## 6. Session Cleanup and Maintenance

### Create Session Cleanup Service

Create `authentication/session_cleanup.py`:

```python
"""
Session cleanup and maintenance service
"""
import asyncio
import logging
from datetime import datetime, timedelta
from chat.session_manager import session_manager

logger = logging.getLogger(__name__)

class SessionCleanupService:
    """Service for maintaining session health and cleanup"""
    
    def __init__(self):
        self.cleanup_interval = 3600  # 1 hour
        self.running = False
    
    async def start_cleanup_service(self):
        """Start the background cleanup service"""
        self.running = True
        logger.info("🧹 Starting session cleanup service")
        
        while self.running:
            try:
                await self.perform_cleanup()
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")
                await asyncio.sleep(60)  # Short retry delay
    
    def stop_cleanup_service(self):
        """Stop the cleanup service"""
        self.running = False
        logger.info("🛑 Stopping session cleanup service")
    
    async def perform_cleanup(self):
        """Perform session cleanup tasks"""
        logger.info("🧹 Performing session cleanup...")
        
        # Clean up expired sessions
        expired_count = await session_manager.cleanup_expired_sessions()
        
        # Get session statistics
        stats = await session_manager.get_session_statistics()
        
        logger.info(f"Session cleanup completed:")
        logger.info(f"  - Expired sessions cleaned: {expired_count}")
        logger.info(f"  - Total active sessions: {stats.get('active_sessions', 0)}")
        logger.info(f"  - Authenticated sessions: {stats.get('authenticated_sessions', 0)}")
        logger.info(f"  - Anonymous sessions: {stats.get('anonymous_sessions', 0)}")
    
    async def cleanup_user_sessions(self, user_id: int, keep_recent: int = 5):
        """Clean up old sessions for a specific user"""
        try:
            # Get user sessions
            sessions = await session_manager.get_user_sessions(
                user_id=user_id,
                active_only=False,
                limit=100
            )
            
            # Sort by last activity and keep only recent ones
            sessions.sort(key=lambda x: x["last_activity"], reverse=True)
            
            if len(sessions) > keep_recent:
                old_sessions = sessions[keep_recent:]
                
                for session in old_sessions:
                    # Deactivate old sessions
                    await session_manager.invalidate_session(session["session_id"])
                
                logger.info(f"Cleaned up {len(old_sessions)} old sessions for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up user sessions: {e}")

# Global cleanup service instance
session_cleanup_service = SessionCleanupService()
```

### Integrate Cleanup Service

Add to your main application startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifecycle with session cleanup"""
    # Startup
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    session_cleanup_task = asyncio.create_task(
        session_cleanup_service.start_cleanup_service()
    )
    print("✅ Started session cleanup services")
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    session_cleanup_service.stop_cleanup_service()
    session_cleanup_task.cancel()
    
    try:
        await cleanup_task
        await session_cleanup_task
    except asyncio.CancelledError:
        pass
        
    print("🛑 Stopped session cleanup services")
```

## 7. Testing Session Management

### Create Session Management Tests

Create `authentication/test_session_management.py`:

```python
"""
Test session management integration
"""
import asyncio
from datetime import datetime, timedelta
from chat.session_manager import session_manager

async def test_session_management():
    """Test enhanced session management"""
    print("🧪 Testing session management integration...")
    
    # Test 1: Create authenticated session
    print("\n1. Testing authenticated session creation...")
    try:
        session_id, session_data, is_new = await session_manager.create_authenticated_session(
            user_id=123,
            username="testuser",
            country="USA",
            service_type="Tax Services",
            auth_method="form",
            remember_me=False
        )
        
        print(f"✅ Created authenticated session: {session_id}")
        print(f"   User ID: {session_data['auth_user_id']}")
        print(f"   Username: {session_data['auth_username']}")
        print(f"   Expires at: {datetime.fromtimestamp(session_data['expires_at'])}")
        
    except Exception as e:
        print(f"❌ Session creation failed: {e}")
        return False
    
    # Test 2: Validate session
    print("\n2. Testing session validation...")
    try:
        validated_session = await session_manager.validate_authenticated_session(
            session_id=session_id,
            session_token=session_data["session_token"],
            user_id=123
        )
        
        if validated_session:
            print("✅ Session validation successful")
        else:
            print("❌ Session validation failed")
            
    except Exception as e:
        print(f"❌ Session validation error: {e}")
    
    # Test 3: Get user sessions
    print("\n3. Testing user session retrieval...")
    try:
        user_sessions = await session_manager.get_user_sessions(user_id=123)
        print(f"✅ Retrieved {len(user_sessions)} sessions for user")
        
        for session in user_sessions:
            print(f"   Session {session['session_id']}: {session['country']} - {session['service_type']}")
            
    except Exception as e:
        print(f"❌ User session retrieval error: {e}")
    
    # Test 4: Session statistics
    print("\n4. Testing session statistics...")
    try:
        stats = await session_manager.get_session_statistics()
        print("✅ Session statistics retrieved:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
            
    except Exception as e:
        print(f"❌ Session statistics error: {e}")
    
    print("\n✅ Session management testing completed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_session_management())
    exit(0 if success else 1)
```

## 8. Security Considerations

### Session Security Configuration

```python
# Add to your main application configuration
SESSION_SECURITY_CONFIG = {
    # Session timeouts
    'default_session_hours': 8,
    'remember_me_days': 30,
    'idle_timeout_minutes': 30,
    
    # Security settings
    'token_length': 32,
    'max_sessions_per_user': 10,
    'session_validation_interval': 300,  # 5 minutes
    
    # Cleanup settings
    'cleanup_interval_hours': 1,
    'keep_expired_sessions_days': 7,
    'max_anonymous_sessions': 1000
}
```

### Session Security Middleware

```python
@app.middleware("http")
async def session_security_middleware(request: Request, call_next):
    """Enhanced session security middleware"""
    
    # Check for session hijacking indicators
    if request.session.get("authenticated"):
        stored_ip = request.session.get("login_ip")
        current_ip = request.client.host
        
        # Simple IP validation (in production, consider more sophisticated checks)
        if stored_ip and stored_ip != current_ip:
            logger.warning(f"Potential session hijacking: {stored_ip} -> {current_ip}")
            # Optionally clear session or require re-authentication
    
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response
```

## 9. Testing and Validation

### Pre-Phase 5 Checklist

- [ ] Database migration completed successfully
- [ ] Enhanced session manager methods work correctly
- [ ] Authenticated sessions can be created and validated
- [ ] Session association with users works
- [ ] User dashboard displays sessions correctly
- [ ] Session cleanup service runs properly
- [ ] Session statistics are accurate
- [ ] Security measures are in place

### Manual Testing Steps

1. **Test Session Creation**:
   ```bash
   python authentication/test_session_management.py
   ```

2. **Test Login Flow**:
   - Login with valid credentials
   - Proceed to country selection
   - Create chat session
   - Verify session is associated with user

3. **Test Dashboard**:
   - Access `/dashboard` after login
   - Verify sessions are displayed
   - Test session continuation

4. **Test Session Security**:
   - Test session expiration
   - Test session token validation
   - Test multiple sessions per user

## Next Steps

After completing this phase:

1. Verify all session management functionality works correctly
2. Test the complete authentication and session flow
3. Monitor session statistics and cleanup processes
4. Proceed to Phase 5: Authentication Middleware Implementation
5. Document any customizations made to the session system

## Security Reminders

1. **Session Token Security**: Never expose session tokens in logs or client-side code
2. **Session Expiration**: Implement proper session timeouts and cleanup
3. **User Association**: Validate user association with sessions on every request
4. **Concurrent Sessions**: Consider limiting concurrent sessions per user
5. **Session Hijacking**: Monitor for suspicious session activity
6. **Database Security**: Ensure session data is properly protected
7. **HTTPS Required**: All session operations must use HTTPS in production