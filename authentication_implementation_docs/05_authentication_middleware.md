# Phase 5: Authentication Middleware Implementation

## Overview

This phase implements comprehensive authentication middleware that automatically protects all FastAPI routes, handles authentication checks, and provides flexible access control. The middleware will create a "login wall" for the entire application while allowing for public endpoints and API access.

## Prerequisites

- Phase 1-4 completed successfully
- Understanding of FastAPI middleware concepts
- Knowledge of HTTP authentication patterns

## 1. Core Authentication Middleware

### Create Authentication Middleware

Create `authentication/middleware.py`:

```python
"""
Authentication middleware for FastAPI application
"""
import logging
import time
from typing import Dict, Any, List, Optional, Set
from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_303_SEE_OTHER
from datetime import datetime
from .dependencies import get_current_user_from_session
from .security_utils import security_utils

logger = logging.getLogger(__name__)

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive authentication middleware for FastAPI
    
    Features:
    - Automatic login wall for protected routes
    - Public route exemptions
    - API vs web page handling
    - Session validation and refresh
    - Security logging
    - Rate limiting integration
    """
    
    def __init__(
        self,
        app,
        public_paths: Optional[Set[str]] = None,
        public_path_patterns: Optional[List[str]] = None,
        api_prefix: str = "/api",
        login_url: str = "/login",
        require_https: bool = False,
        log_auth_events: bool = True
    ):
        super().__init__(app)
        
        # Default public paths that don't require authentication
        self.public_paths = public_paths or {
            "/login",
            "/logout", 
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/favicon.ico"
        }
        
        # Path patterns that are public (support wildcards)
        self.public_path_patterns = public_path_patterns or [
            "/static/*",
            "/assets/*",
            "/.well-known/*"
        ]
        
        self.api_prefix = api_prefix
        self.login_url = login_url
        self.require_https = require_https
        self.log_auth_events = log_auth_events
        
        # Performance tracking
        self.auth_check_times = []
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public and doesn't require authentication"""
        
        # Check exact matches
        if path in self.public_paths:
            return True
        
        # Check pattern matches
        for pattern in self.public_path_patterns:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return True
            elif pattern == path:
                return True
        
        return False
    
    def _is_api_request(self, path: str) -> bool:
        """Check if request is to API endpoint"""
        return path.startswith(self.api_prefix)
    
    def _should_redirect_to_login(self, request: Request) -> bool:
        """Determine if request should redirect to login page"""
        
        # Only redirect GET requests to web pages
        if request.method != "GET":
            return False
        
        # Don't redirect API requests
        if self._is_api_request(request.url.path):
            return False
        
        # Don't redirect if already going to login
        if request.url.path == self.login_url:
            return False
        
        return True
    
    def _log_auth_event(self, event_type: str, request: Request, details: Dict[str, Any] = None):
        """Log authentication events for security monitoring"""
        
        if not self.log_auth_events:
            return
        
        log_data = {
            "event": event_type,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            log_data.update(details)
        
        if event_type in ["auth_required", "session_expired", "auth_failed"]:
            logger.warning(f"AUTH_EVENT: {log_data}")
        else:
            logger.info(f"AUTH_EVENT: {log_data}")
    
    def _create_auth_response(self, request: Request, error_message: str = None) -> Response:
        """Create appropriate response for unauthenticated requests"""
        
        if self._should_redirect_to_login(request):
            # Store original URL for post-login redirect
            request.session["redirect_after_login"] = str(request.url)
            
            self._log_auth_event("redirect_to_login", request, {
                "original_url": str(request.url)
            })
            
            return RedirectResponse(
                url=self.login_url,
                status_code=HTTP_303_SEE_OTHER
            )
        else:
            # Return 401 for API requests or non-GET requests
            self._log_auth_event("auth_required", request, {
                "error": error_message or "Authentication required"
            })
            
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail=error_message or "Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Main middleware dispatch method"""
        
        start_time = time.time()
        
        try:
            # Security check: HTTPS requirement
            if self.require_https and request.url.scheme != "https":
                logger.warning(f"HTTP request blocked: {request.url}")
                raise HTTPException(
                    status_code=400,
                    detail="HTTPS required"
                )
            
            # Check if path is public
            if self._is_public_path(request.url.path):
                response = await call_next(request)
                return response
            
            # Get current authenticated user
            current_user = await get_current_user_from_session(request)
            
            if not current_user:
                # User not authenticated
                self._log_auth_event("unauthenticated_access", request)
                return self._create_auth_response(
                    request,
                    "Please sign in to access this resource"
                )
            
            # Add user context to request state for use in endpoints
            request.state.current_user = current_user
            
            # Log successful authentication check
            if self.log_auth_events:
                auth_time = time.time() - start_time
                self.auth_check_times.append(auth_time)
                
                # Keep only last 100 measurements for performance monitoring
                if len(self.auth_check_times) > 100:
                    self.auth_check_times.pop(0)
            
            # Process the request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response, current_user)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            self._log_auth_event("middleware_error", request, {
                "error": str(e)
            })
            
            # Continue processing on middleware errors
            response = await call_next(request)
            return response
    
    def _add_security_headers(self, response: Response, user: Dict[str, Any]):
        """Add security headers to response"""
        
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add user-specific headers if needed
        if user:
            response.headers["X-User-Authenticated"] = "true"
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get middleware performance statistics"""
        
        if not self.auth_check_times:
            return {"auth_checks": 0}
        
        return {
            "auth_checks": len(self.auth_check_times),
            "avg_auth_time_ms": sum(self.auth_check_times) / len(self.auth_check_times) * 1000,
            "max_auth_time_ms": max(self.auth_check_times) * 1000,
            "min_auth_time_ms": min(self.auth_check_times) * 1000
        }
```

## 2. Route-Specific Authentication Control

### Create Authentication Decorators

Create `authentication/decorators.py`:

```python
"""
Authentication decorators and route protection utilities
"""
from functools import wraps
from typing import Optional, List, Callable, Any
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from .dependencies import get_current_user_from_session

def public_route(func: Callable) -> Callable:
    """
    Decorator to mark a route as public (bypass authentication middleware)
    
    Usage:
    @app.get("/public-endpoint")
    @public_route
    async def public_endpoint():
        return {"message": "This endpoint is public"}
    """
    func._is_public = True
    return func

def require_auth(
    redirect_url: Optional[str] = "/login",
    api_response: bool = False
) -> Callable:
    """
    Decorator to require authentication for specific routes
    
    Args:
        redirect_url: URL to redirect unauthenticated users (web requests)
        api_response: If True, return 401 instead of redirecting
    
    Usage:
    @app.get("/protected")
    @require_auth()
    async def protected_endpoint(request: Request):
        user = request.state.current_user
        return {"user": user["username"]}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from args (assuming it's the first parameter)
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                raise HTTPException(500, "Request object not found in route")
            
            # Check authentication
            user = await get_current_user_from_session(request)
            if not user:
                if api_response or request.url.path.startswith("/api/"):
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                else:
                    request.session["redirect_after_login"] = str(request.url)
                    return RedirectResponse(url=redirect_url, status_code=303)
            
            # Add user to request state
            request.state.current_user = user
            
            # Call original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def require_roles(
    roles: List[str],
    require_all: bool = False
) -> Callable:
    """
    Decorator to require specific roles (if role system is implemented)
    
    Args:
        roles: List of required roles
        require_all: If True, user must have ALL roles; if False, ANY role
    
    Usage:
    @app.get("/admin")
    @require_roles(["admin", "manager"])
    async def admin_endpoint(request: Request):
        return {"message": "Admin access granted"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                raise HTTPException(500, "Request object not found")
            
            user = await get_current_user_from_session(request)
            if not user:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check roles (this would need to be implemented based on your user system)
            user_roles = user.get("roles", [])
            
            if require_all:
                has_access = all(role in user_roles for role in roles)
            else:
                has_access = any(role in user_roles for role in roles)
            
            if not has_access:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {', '.join(roles)}"
                )
            
            request.state.current_user = user
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

class AuthenticationDependency:
    """
    Class-based authentication dependency with configurable options
    """
    
    def __init__(
        self,
        required: bool = True,
        redirect_url: str = "/login",
        api_response: bool = False,
        roles: Optional[List[str]] = None
    ):
        self.required = required
        self.redirect_url = redirect_url
        self.api_response = api_response
        self.roles = roles or []
    
    async def __call__(self, request: Request) -> Optional[Dict[str, Any]]:
        """Dependency callable"""
        
        user = await get_current_user_from_session(request)
        
        if self.required and not user:
            if self.api_response or request.url.path.startswith("/api/"):
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            else:
                request.session["redirect_after_login"] = str(request.url)
                return RedirectResponse(url=self.redirect_url, status_code=303)
        
        # Check roles if specified
        if user and self.roles:
            user_roles = user.get("roles", [])
            if not any(role in user_roles for role in self.roles):
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail=f"Required roles: {', '.join(self.roles)}"
                )
        
        return user

# Pre-configured dependency instances
RequireAuth = AuthenticationDependency(required=True)
OptionalAuth = AuthenticationDependency(required=False)
AdminAuth = AuthenticationDependency(required=True, roles=["admin"])
```

## 3. Public Route Configuration

### Create Route Configuration

Create `authentication/route_config.py`:

```python
"""
Route configuration for authentication middleware
"""
from typing import Set, List, Dict, Any

class RouteConfig:
    """Configuration for route-based authentication"""
    
    # Paths that are always public (no authentication required)
    PUBLIC_PATHS: Set[str] = {
        # Authentication endpoints
        "/login",
        "/logout",
        "/sso-login",
        
        # Documentation and health
        "/docs",
        "/redoc", 
        "/openapi.json",
        "/health",
        "/status",
        
        # Static files
        "/favicon.ico",
        "/robots.txt",
        "/sitemap.xml",
    }
    
    # Path patterns that are public (support wildcards)
    PUBLIC_PATH_PATTERNS: List[str] = [
        "/static/*",
        "/assets/*", 
        "/media/*",
        "/.well-known/*",
        "/api/public/*"
    ]
    
    # API endpoints that require authentication but return JSON errors
    API_PATHS: Set[str] = {
        "/api/",
        "/api/v1/",
        "/graphql/"
    }
    
    # Special handling for different route types
    ROUTE_HANDLERS: Dict[str, Dict[str, Any]] = {
        "/": {
            "auth_required": True,
            "redirect_to": "/country/",
            "description": "Root endpoint redirects to country selection"
        },
        "/country/": {
            "auth_required": True,
            "description": "Country selection page"
        },
        "/chat/": {
            "auth_required": True,
            "session_required": True,
            "description": "Chat interface"
        },
        "/dashboard": {
            "auth_required": True,
            "description": "User dashboard"
        }
    }
    
    @classmethod
    def is_public_path(cls, path: str) -> bool:
        """Check if path is public"""
        
        # Check exact matches
        if path in cls.PUBLIC_PATHS:
            return True
        
        # Check pattern matches
        for pattern in cls.PUBLIC_PATH_PATTERNS:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return True
            elif pattern == path:
                return True
        
        return False
    
    @classmethod
    def is_api_path(cls, path: str) -> bool:
        """Check if path is an API endpoint"""
        return any(path.startswith(api_path) for api_path in cls.API_PATHS)
    
    @classmethod
    def get_route_config(cls, path: str) -> Dict[str, Any]:
        """Get configuration for specific route"""
        return cls.ROUTE_HANDLERS.get(path, {
            "auth_required": True,
            "description": "Protected route"
        })
    
    @classmethod
    def add_public_path(cls, path: str):
        """Dynamically add a public path"""
        cls.PUBLIC_PATHS.add(path)
    
    @classmethod
    def add_public_pattern(cls, pattern: str):
        """Dynamically add a public path pattern"""
        cls.PUBLIC_PATH_PATTERNS.append(pattern)
```

## 4. Advanced Authentication Features

### Create Advanced Authentication Utils

Create `authentication/advanced_auth.py`:

```python
"""
Advanced authentication features
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from .security_utils import security_utils
from chat.session_manager import session_manager

class AdvancedAuthManager:
    """Advanced authentication management features"""
    
    def __init__(self):
        self.active_sessions = defaultdict(set)  # user_id -> set of session_ids
        self.session_activity = defaultdict(list)  # session_id -> list of activities
        self.concurrent_login_alerts = defaultdict(int)
    
    async def track_user_login(
        self,
        user_id: int,
        session_id: str,
        login_info: Dict[str, Any]
    ):
        """Track user login for security monitoring"""
        
        # Add to active sessions
        self.active_sessions[user_id].add(session_id)
        
        # Track login activity
        activity = {
            "type": "login",
            "timestamp": datetime.now().isoformat(),
            "ip": login_info.get("ip"),
            "user_agent": login_info.get("user_agent"),
            "session_id": session_id
        }
        
        self.session_activity[session_id].append(activity)
        
        # Check for concurrent logins
        active_count = len(self.active_sessions[user_id])
        if active_count > 3:  # Alert on more than 3 concurrent sessions
            self.concurrent_login_alerts[user_id] += 1
            await self._send_security_alert(user_id, "multiple_sessions", {
                "active_sessions": active_count,
                "new_session": session_id
            })
    
    async def track_user_logout(self, user_id: int, session_id: str):
        """Track user logout"""
        
        # Remove from active sessions
        if user_id in self.active_sessions:
            self.active_sessions[user_id].discard(session_id)
            
            # Clean up if no active sessions
            if not self.active_sessions[user_id]:
                del self.active_sessions[user_id]
        
        # Track logout activity
        activity = {
            "type": "logout",
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        self.session_activity[session_id].append(activity)
    
    async def check_session_security(
        self,
        session_id: str,
        current_ip: str,
        user_agent: str
    ) -> Dict[str, Any]:
        """Check session for security anomalies"""
        
        activities = self.session_activity.get(session_id, [])
        if not activities:
            return {"status": "no_history", "risk_level": "low"}
        
        # Check for IP changes
        last_login = next((a for a in reversed(activities) if a["type"] == "login"), None)
        if last_login and last_login.get("ip") != current_ip:
            return {
                "status": "ip_change",
                "risk_level": "medium",
                "details": {
                    "original_ip": last_login.get("ip"),
                    "current_ip": current_ip
                }
            }
        
        # Check for user agent changes
        if last_login and last_login.get("user_agent") != user_agent:
            return {
                "status": "user_agent_change", 
                "risk_level": "low",
                "details": {
                    "original_ua": last_login.get("user_agent"),
                    "current_ua": user_agent
                }
            }
        
        return {"status": "normal", "risk_level": "low"}
    
    async def get_user_security_summary(self, user_id: int) -> Dict[str, Any]:
        """Get security summary for a user"""
        
        active_sessions = list(self.active_sessions.get(user_id, set()))
        
        # Get session details
        session_details = []
        for session_id in active_sessions:
            session_data = await session_manager.get_session(session_id)
            if session_data:
                activities = self.session_activity.get(session_id, [])
                last_activity = activities[-1] if activities else None
                
                session_details.append({
                    "session_id": session_id,
                    "country": session_data.get("country"),
                    "service_type": session_data.get("service_type"),
                    "created_at": session_data.get("created_at"),
                    "last_activity": last_activity
                })
        
        return {
            "user_id": user_id,
            "active_sessions_count": len(active_sessions),
            "concurrent_login_alerts": self.concurrent_login_alerts.get(user_id, 0),
            "session_details": session_details,
            "risk_assessment": "low" if len(active_sessions) <= 2 else "medium"
        }
    
    async def force_logout_user(self, user_id: int, except_session: str = None) -> int:
        """Force logout all sessions for a user"""
        
        sessions_to_logout = self.active_sessions.get(user_id, set()).copy()
        if except_session:
            sessions_to_logout.discard(except_session)
        
        # Invalidate sessions in database
        count = await session_manager.invalidate_user_sessions(
            user_id=user_id,
            except_session_id=except_session
        )
        
        # Update tracking
        for session_id in sessions_to_logout:
            await self.track_user_logout(user_id, session_id)
        
        return count
    
    async def _send_security_alert(
        self,
        user_id: int,
        alert_type: str,
        details: Dict[str, Any]
    ):
        """Send security alert (implement based on your notification system)"""
        
        alert = {
            "user_id": user_id,
            "alert_type": alert_type,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        
        # Log the alert
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"SECURITY_ALERT: {json.dumps(alert)}")
        
        # Here you could integrate with email, Slack, or other notification systems
        # await send_email_alert(user_id, alert)
        # await send_slack_alert(alert)

# Global instance
advanced_auth_manager = AdvancedAuthManager()
```

## 5. Integration with Main Application

### Update Main Application

Modify your `main.py` to integrate the authentication middleware:

```python
from authentication.middleware import AuthenticationMiddleware
from authentication.route_config import RouteConfig
from authentication.advanced_auth import advanced_auth_manager

# Add authentication middleware to FastAPI app
app.add_middleware(
    AuthenticationMiddleware,
    public_paths=RouteConfig.PUBLIC_PATHS,
    public_path_patterns=RouteConfig.PUBLIC_PATH_PATTERNS,
    api_prefix="/api",
    login_url="/login",
    require_https=False,  # Set to True in production
    log_auth_events=True
)

# Update existing routes to use middleware-provided user context
@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page(request: Request):
    """Country selection page - automatically protected by middleware"""
    
    # Get user from middleware (available in request.state)
    current_user = request.state.current_user
    username = current_user["username"]
    
    # Your existing country selection logic...
    # The middleware already ensured the user is authenticated
    
    return f"""
    <!-- Your existing HTML with user info -->
    <div style="text-align: right; padding: 10px; background: #f8f9fa;">
        Welcome, <strong>{username}</strong> | 
        <a href="/dashboard">Dashboard</a> |
        <form method="post" action="/logout" style="display: inline;">
            <button type="submit" style="background: none; border: none; color: #198484; cursor: pointer;">
                Logout
            </button>
        </form>
    </div>
    <!-- Rest of your HTML -->
    """

@app.get("/chat/", response_class=HTMLResponse) 
async def chat_interface_page(request: Request, session_id: str = None):
    """Chat interface - automatically protected by middleware"""
    
    current_user = request.state.current_user
    
    # Validate session belongs to user
    session_data = await session_manager.validate_authenticated_session(
        session_id=session_id,
        user_id=current_user["user_id"]
    )
    
    if not session_data:
        raise HTTPException(404, "Invalid session or session does not belong to user")
    
    # Track session activity
    await advanced_auth_manager.track_user_login(
        user_id=current_user["user_id"],
        session_id=session_id,
        login_info={
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent")
        }
    )
    
    # Your existing chat interface logic...

# Add security monitoring endpoints
@app.get("/api/auth/security-summary")
async def get_security_summary(request: Request):
    """Get security summary for current user"""
    
    current_user = request.state.current_user
    summary = await advanced_auth_manager.get_user_security_summary(
        current_user["user_id"]
    )
    
    return summary

@app.post("/api/auth/logout-all-sessions")
async def logout_all_sessions(request: Request):
    """Logout all sessions except current one"""
    
    current_user = request.state.current_user
    current_session = request.session.get("chat_session_id")
    
    count = await advanced_auth_manager.force_logout_user(
        user_id=current_user["user_id"],
        except_session=current_session
    )
    
    return {"logged_out_sessions": count}
```

## 6. Error Handling and Logging

### Create Authentication Error Handler

Create `authentication/error_handlers.py`:

```python
"""
Error handlers for authentication system
"""
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

async def authentication_error_handler(request: Request, exc: HTTPException):
    """Handle authentication errors"""
    
    # Log the error
    logger.warning(f"Authentication error: {exc.status_code} - {exc.detail} - Path: {request.url.path}")
    
    # Check if it's an API request
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "authentication_required",
                "message": exc.detail,
                "login_url": "/login"
            }
        )
    
    # For web requests, redirect to login or show error page
    if exc.status_code == HTTP_401_UNAUTHORIZED:
        # Store original URL for post-login redirect
        if request.method == "GET":
            request.session["redirect_after_login"] = str(request.url)
        
        return RedirectResponse(url="/login", status_code=303)
    
    elif exc.status_code == HTTP_403_FORBIDDEN:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Access Denied",
            "message": exc.detail or "You don't have permission to access this resource.",
            "status_code": 403
        }, status_code=403)
    
    # Generic error response
    return templates.TemplateResponse("error.html", {
        "request": request,
        "title": "Authentication Error",
        "message": exc.detail or "An authentication error occurred.",
        "status_code": exc.status_code
    }, status_code=exc.status_code)

# Add to main application
# app.add_exception_handler(HTTP_401_UNAUTHORIZED, authentication_error_handler)
# app.add_exception_handler(HTTP_403_FORBIDDEN, authentication_error_handler)
```

## 7. Performance Monitoring

### Create Performance Monitor

Create `authentication/performance_monitor.py`:

```python
"""
Performance monitoring for authentication system
"""
import asyncio
import time
import json
from typing import Dict, List, Any
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)

class AuthPerformanceMonitor:
    """Monitor authentication system performance"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        
        # Performance metrics
        self.auth_check_times = deque(maxlen=max_samples)
        self.session_validation_times = deque(maxlen=max_samples)
        self.login_times = deque(maxlen=max_samples)
        
        # Request tracking
        self.request_counts = {
            "total": 0,
            "authenticated": 0,
            "unauthenticated": 0,
            "redirected": 0,
            "api_requests": 0
        }
        
        # Error tracking
        self.error_counts = {
            "auth_failures": 0,
            "session_expired": 0,
            "invalid_sessions": 0,
            "middleware_errors": 0
        }
        
        # Performance alerts
        self.performance_alerts = []
        self.alert_thresholds = {
            "auth_check_ms": 50,  # Alert if auth check takes > 50ms
            "session_validation_ms": 100,  # Alert if session validation > 100ms
            "login_ms": 1000  # Alert if login takes > 1000ms
        }
    
    def record_auth_check(self, duration_ms: float):
        """Record authentication check time"""
        self.auth_check_times.append(duration_ms)
        
        if duration_ms > self.alert_thresholds["auth_check_ms"]:
            self._create_performance_alert(
                "slow_auth_check",
                f"Auth check took {duration_ms:.2f}ms"
            )
    
    def record_session_validation(self, duration_ms: float):
        """Record session validation time"""
        self.session_validation_times.append(duration_ms)
        
        if duration_ms > self.alert_thresholds["session_validation_ms"]:
            self._create_performance_alert(
                "slow_session_validation",
                f"Session validation took {duration_ms:.2f}ms"
            )
    
    def record_login(self, duration_ms: float):
        """Record login time"""
        self.login_times.append(duration_ms)
        
        if duration_ms > self.alert_thresholds["login_ms"]:
            self._create_performance_alert(
                "slow_login",
                f"Login took {duration_ms:.2f}ms"
            )
    
    def increment_request_count(self, request_type: str):
        """Increment request counter"""
        if request_type in self.request_counts:
            self.request_counts[request_type] += 1
        self.request_counts["total"] += 1
    
    def increment_error_count(self, error_type: str):
        """Increment error counter"""
        if error_type in self.error_counts:
            self.error_counts[error_type] += 1
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        
        def calculate_stats(times: deque) -> Dict[str, float]:
            if not times:
                return {"count": 0}
            
            times_list = list(times)
            return {
                "count": len(times_list),
                "avg": sum(times_list) / len(times_list),
                "min": min(times_list),
                "max": max(times_list),
                "p95": sorted(times_list)[int(len(times_list) * 0.95)] if len(times_list) > 20 else max(times_list)
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "auth_check_times": calculate_stats(self.auth_check_times),
            "session_validation_times": calculate_stats(self.session_validation_times),
            "login_times": calculate_stats(self.login_times),
            "request_counts": self.request_counts.copy(),
            "error_counts": self.error_counts.copy(),
            "recent_alerts": self.performance_alerts[-10:],  # Last 10 alerts
            "health_score": self._calculate_health_score()
        }
    
    def _calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0
        
        # Deduct points for slow performance
        if self.auth_check_times:
            avg_auth_time = sum(self.auth_check_times) / len(self.auth_check_times)
            if avg_auth_time > 25:  # > 25ms
                score -= min(20, (avg_auth_time - 25) / 2)
        
        # Deduct points for errors
        total_requests = self.request_counts["total"]
        if total_requests > 0:
            error_rate = sum(self.error_counts.values()) / total_requests
            score -= min(30, error_rate * 100 * 3)  # Up to 30 points for errors
        
        # Deduct points for recent alerts
        recent_alerts = len([a for a in self.performance_alerts 
                           if datetime.fromisoformat(a["timestamp"]) > datetime.now() - timedelta(minutes=10)])
        score -= min(20, recent_alerts * 2)
        
        return max(0, score)
    
    def _create_performance_alert(self, alert_type: str, message: str):
        """Create a performance alert"""
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        self.performance_alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.performance_alerts) > 100:
            self.performance_alerts.pop(0)
        
        logger.warning(f"PERFORMANCE_ALERT: {json.dumps(alert)}")
    
    async def start_monitoring(self, interval_seconds: int = 300):
        """Start periodic performance monitoring"""
        while True:
            try:
                stats = self.get_performance_stats()
                logger.info(f"AUTH_PERFORMANCE: {json.dumps(stats)}")
                
                # Check for critical performance issues
                health_score = stats["health_score"]
                if health_score < 70:
                    self._create_performance_alert(
                        "poor_health_score",
                        f"Authentication system health score: {health_score:.1f}"
                    )
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute

# Global performance monitor
auth_performance_monitor = AuthPerformanceMonitor()
```

## 8. Testing Authentication Middleware

### Create Middleware Tests

Create `authentication/test_middleware.py`:

```python
"""
Test authentication middleware functionality
"""
import asyncio
from fastapi.testclient import TestClient
from authentication.middleware import AuthenticationMiddleware
from authentication.route_config import RouteConfig

# Mock FastAPI app for testing
from fastapi import FastAPI, Request

test_app = FastAPI()

# Add test routes
@test_app.get("/public")
async def public_route():
    return {"message": "This is a public route"}

@test_app.get("/protected")
async def protected_route(request: Request):
    user = getattr(request.state, 'current_user', None)
    return {"message": "This is protected", "user": user}

@test_app.get("/api/test")
async def api_route():
    return {"message": "API endpoint"}

# Add middleware
RouteConfig.add_public_path("/public")
test_app.add_middleware(
    AuthenticationMiddleware,
    public_paths=RouteConfig.PUBLIC_PATHS,
    public_path_patterns=RouteConfig.PUBLIC_PATH_PATTERNS,
    login_url="/login"
)

async def test_middleware_functionality():
    """Test middleware functionality"""
    print("🧪 Testing authentication middleware...")
    
    client = TestClient(test_app)
    
    # Test 1: Public route should be accessible
    print("\n1. Testing public route access...")
    response = client.get("/public")
    if response.status_code == 200:
        print("✅ Public route accessible without authentication")
    else:
        print(f"❌ Public route failed: {response.status_code}")
    
    # Test 2: Protected route should redirect to login
    print("\n2. Testing protected route redirect...")
    response = client.get("/protected", follow_redirects=False)
    if response.status_code == 303 and "/login" in response.headers.get("location", ""):
        print("✅ Protected route redirects to login")
    else:
        print(f"❌ Protected route response: {response.status_code}")
    
    # Test 3: API route should return 401
    print("\n3. Testing API route authentication...")
    response = client.get("/api/test")
    if response.status_code == 401:
        print("✅ API route returns 401 for unauthenticated request")
    else:
        print(f"❌ API route response: {response.status_code}")
    
    print("\n✅ Middleware testing completed!")

if __name__ == "__main__":
    asyncio.run(test_middleware_functionality())
```

## 9. Production Configuration

### Environment Configuration

Add to your `.env` file:

```bash
# Authentication Middleware Configuration
AUTH_REQUIRE_HTTPS=true
AUTH_LOG_EVENTS=true
AUTH_PERFORMANCE_MONITORING=true

# Security Settings
AUTH_SESSION_TIMEOUT_HOURS=8
AUTH_REMEMBER_ME_DAYS=30
AUTH_MAX_SESSIONS_PER_USER=5
AUTH_FORCE_LOGOUT_ON_IP_CHANGE=false

# Performance Thresholds
AUTH_CHECK_TIMEOUT_MS=50
SESSION_VALIDATION_TIMEOUT_MS=100
LOGIN_TIMEOUT_MS=1000

# Rate Limiting
AUTH_MAX_LOGIN_ATTEMPTS=5
AUTH_LOCKOUT_DURATION_MINUTES=15
AUTH_RATE_LIMIT_WINDOW_MINUTES=15
```

### Production Logging Configuration

```python
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'auth_formatter': {
            'format': '[{asctime}] AUTH {levelname}: {message}',
            'style': '{',
        },
        'performance_formatter': {
            'format': '[{asctime}] PERF {levelname}: {message}',
            'style': '{',
        }
    },
    'handlers': {
        'auth_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/auth.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 10,
            'formatter': 'auth_formatter',
        },
        'performance_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/performance.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 5,
            'formatter': 'performance_formatter',
        }
    },
    'loggers': {
        'authentication': {
            'handlers': ['auth_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'performance': {
            'handlers': ['performance_file'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}
```

## 10. Testing and Validation

### Pre-Phase 6 Checklist

- [ ] Authentication middleware installed and configured
- [ ] Public routes properly exempted from authentication
- [ ] Protected routes require authentication
- [ ] API endpoints return 401 instead of redirecting
- [ ] Session validation integrated with middleware
- [ ] Performance monitoring active
- [ ] Error handling works correctly
- [ ] Logging configured properly

### Manual Testing Steps

1. **Test Public Access**:
   - Visit `/login`, `/docs`, `/health`
   - Should be accessible without authentication

2. **Test Authentication Wall**:
   - Try accessing `/country/`, `/chat/`, `/dashboard`
   - Should redirect to login page

3. **Test API Authentication**:
   - Make API requests to protected endpoints
   - Should return 401 JSON responses

4. **Test Session Integration**:
   - Login and verify session works across routes
   - Test session expiration

### Performance Testing

```bash
# Test authentication performance
python authentication/test_middleware.py

# Monitor performance in logs
tail -f logs/performance.log

# Check health metrics
curl http://localhost:8000/api/auth/performance-stats
```

## Next Steps

After completing this phase:

1. Verify middleware protects all routes correctly
2. Test performance under load
3. Monitor authentication logs
4. Proceed to Phase 6: JWT SSO Integration
5. Document any middleware customizations

## Security Reminders

1. **HTTPS Required**: Always use HTTPS in production
2. **Secure Headers**: Middleware adds security headers automatically
3. **Session Security**: Validate sessions on every request
4. **Performance**: Monitor authentication performance
5. **Logging**: Log all security events appropriately
6. **Error Handling**: Don't expose sensitive information in errors
7. **Rate Limiting**: Implement proper rate limiting for login attempts