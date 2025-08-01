# Phase 3: Login System Implementation

## Overview

This phase implements the login form UI and authentication endpoints in FastAPI. The system will provide a custom login page that integrates with the existing application flow and handles form submission with proper error handling.

## Prerequisites

- Phase 1 (Database Setup) completed
- Phase 2 (Password Verification) completed
- FastAPI application with existing routes
- Understanding of HTML forms and FastAPI templating

## 1. Login Form Dependencies

### Install Additional Dependencies

```bash
pip install jinja2 python-multipart
```

### Import Required Modules

Add to your existing imports in `main.py`:

```python
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER
import os
```

## 2. Login Page Implementation

### Create Login Template

Create `templates/login.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Growbal Intelligence - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', Arial, sans-serif;
            background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            max-width: 400px;
            width: 90%;
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1);
            text-align: center;
        }
        .logo-container {
            margin-bottom: 30px;
        }
        .app-header {
            background: linear-gradient(135deg, #2b5556 0%, #21908f 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
        }
        .app-title {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .app-description {
            font-size: 1rem;
            opacity: 0.9;
        }
        .login-form {
            text-align: left;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            font-weight: 600;
            color: #2b5556;
            margin-bottom: 8px;
            font-size: 1rem;
        }
        .form-input {
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 2px solid rgba(25, 132, 132, 0.2);
            border-radius: 10px;
            background: white;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        .form-input:focus {
            border-color: #198484;
            box-shadow: 0 0 0 3px rgba(25, 132, 132, 0.1);
            outline: none;
        }
        .form-input.error {
            border-color: #dc3545;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .checkbox-input {
            margin-right: 10px;
            transform: scale(1.2);
        }
        .checkbox-label {
            font-size: 0.9rem;
            color: #666;
        }
        .btn-primary {
            background: linear-gradient(135deg, #198484 0%, #16a6a6 100%);
            border: none;
            color: white;
            font-weight: 600;
            border-radius: 10px;
            padding: 15px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(25, 132, 132, 0.2);
            width: 100%;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(25, 132, 132, 0.3);
            background: linear-gradient(135deg, #16a6a6 0%, #198484 100%);
        }
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #f5c6cb;
            font-size: 0.9rem;
        }
        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #c3e6cb;
            font-size: 0.9rem;
        }
        .forgot-password {
            text-align: center;
            margin-top: 20px;
        }
        .forgot-password a {
            color: #198484;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .forgot-password a:hover {
            text-decoration: underline;
        }
        .back-link {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid rgba(25, 132, 132, 0.1);
        }
        .back-link a {
            color: #198484;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .back-link a:hover {
            text-decoration: underline;
        }
        .loading {
            display: none;
            align-items: center;
            justify-content: center;
            margin-top: 10px;
        }
        .spinner {
            border: 2px solid #f3f3f3;
            border-top: 2px solid #198484;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @media (max-width: 768px) {
            .login-container {
                width: 95%;
                padding: 30px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <!-- Logo placeholder - replace with your logo -->
        <div class="logo-container">
            <!-- Logo SVG content will be inserted here -->
        </div>
        
        <div class="app-header">
            <h1 class="app-title">Growbal Intelligence</h1>
            <p class="app-description">Please sign in to continue</p>
        </div>
        
        <!-- Error message display -->
        {% if error %}
        <div class="error-message">
            {{ error }}
        </div>
        {% endif %}
        
        <!-- Success message display -->
        {% if success %}
        <div class="success-message">
            {{ success }}
        </div>
        {% endif %}
        
        <form class="login-form" method="post" action="/login" id="loginForm">
            <div class="form-group">
                <label for="username" class="form-label">Username or Email</label>
                <input 
                    type="text" 
                    id="username" 
                    name="username" 
                    class="form-input" 
                    required 
                    value="{{ username or '' }}"
                    autocomplete="username"
                    placeholder="Enter your username or email"
                >
            </div>
            
            <div class="form-group">
                <label for="password" class="form-label">Password</label>
                <input 
                    type="password" 
                    id="password" 
                    name="password" 
                    class="form-input" 
                    required
                    autocomplete="current-password"
                    placeholder="Enter your password"
                >
            </div>
            
            <div class="checkbox-group">
                <input type="checkbox" id="remember_me" name="remember_me" class="checkbox-input">
                <label for="remember_me" class="checkbox-label">Remember me for 30 days</label>
            </div>
            
            <button type="submit" class="btn-primary" id="loginButton">
                Sign In
            </button>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <span>Signing in...</span>
            </div>
        </form>
        
        <div class="forgot-password">
            <a href="#" onclick="alert('Contact your administrator for password reset')">
                Forgot your password?
            </a>
        </div>
        
        <div class="back-link">
            <a href="/country/">← Back to Country Selection</a>
        </div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', function() {
            const button = document.getElementById('loginButton');
            const loading = document.getElementById('loading');
            
            button.style.display = 'none';
            loading.style.display = 'flex';
        });
        
        // Auto-focus username field
        document.getElementById('username').focus();
        
        // Clear error styling on input
        document.querySelectorAll('.form-input').forEach(input => {
            input.addEventListener('input', function() {
                this.classList.remove('error');
            });
        });
    </script>
</body>
</html>
```

### Setup Templates Directory

In your main application file, add template configuration:

```python
# Add to imports
from fastapi.templating import Jinja2Templates

# Add after FastAPI app creation
templates = Jinja2Templates(directory="templates")
```

## 3. Login Endpoints Implementation

### Add Login Routes to Main Application

Add these routes to your `main.py` (or create separate `auth_routes.py`):

```python
from authentication.auth_service import auth_service
from authentication.models import LoginRequest
from authentication.security_utils import security_utils

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, success: str = None):
    """Serve the login page"""
    
    # Check if user is already authenticated
    if request.session.get("authenticated"):
        # Redirect to original destination or home
        redirect_url = request.session.get("redirect_after_login", "/country/")
        return RedirectResponse(url=redirect_url, status_code=HTTP_303_SEE_OTHER)
    
    # Read logo file if exists
    logo_html = ""
    logo_path = os.path.join(os.path.dirname(__file__), "growbal_logoheader.svg")
    if os.path.exists(logo_path):
        with open(logo_path, 'r') as f:
            logo_content = f.read()
            logo_html = f"""
            <div style="max-width: 150px; height: auto; margin: 0 auto;">
                {logo_content}
            </div>
            """
    
    # Inject logo into template (basic approach)
    # In production, you'd use Jinja2 template inheritance
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "success": success,
        "logo_html": logo_html
    })

@app.post("/login")
async def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: bool = Form(False)
):
    """Handle login form submission"""
    
    # Get client IP for rate limiting
    client_ip = request.client.host
    
    # Check rate limiting
    if security_utils.is_rate_limited(client_ip, max_attempts=5, window_minutes=15):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Too many login attempts. Please try again in 15 minutes.",
            "username": username
        })
    
    # Validate input
    if not security_utils.validate_input_safety(username) or not security_utils.validate_input_safety(password):
        security_utils.record_failed_attempt(client_ip)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid input detected.",
            "username": username
        })
    
    # Create login request
    login_request = LoginRequest(
        username=username.strip(),
        password=password,
        remember_me=remember_me
    )
    
    try:
        # Authenticate user
        auth_result = await auth_service.authenticate_user(login_request)
        
        if auth_result.success:
            # Clear failed attempts
            security_utils.clear_failed_attempts(client_ip)
            
            # Store authentication info in session
            request.session["authenticated"] = True
            request.session["user_id"] = auth_result.user.user_id
            request.session["username"] = auth_result.user.username
            request.session["auth_method"] = "form"
            
            # Set session expiration based on remember_me
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
            
            # Redirect to original destination or country selection
            redirect_url = request.session.get("redirect_after_login", "/country/")
            request.session.pop("redirect_after_login", None)
            
            return RedirectResponse(url=redirect_url, status_code=HTTP_303_SEE_OTHER)
        
        else:
            # Record failed attempt
            security_utils.record_failed_attempt(client_ip)
            
            # Log failed attempt
            logger.warning(f"Failed login attempt: {username} from {client_ip}")
            
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": auth_result.error_message,
                "username": username
            })
    
    except Exception as e:
        # Record failed attempt
        security_utils.record_failed_attempt(client_ip)
        
        # Log error
        logger.error(f"Login error for {username}: {e}")
        
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Login service temporarily unavailable. Please try again later.",
            "username": username
        })

@app.post("/logout")
async def logout(request: Request):
    """Handle user logout"""
    
    # Log logout
    username = request.session.get("username", "unknown")
    logger.info(f"User logout: {username}")
    
    # Clear session
    request.session.clear()
    
    # Redirect to login page with success message
    return RedirectResponse(
        url="/login?success=You have been successfully logged out.",
        status_code=HTTP_303_SEE_OTHER
    )
```

## 4. Authentication Dependency

### Create Authentication Dependency

Create `authentication/dependencies.py`:

```python
"""
FastAPI dependencies for authentication
"""
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_303_SEE_OTHER
from typing import Dict, Any, Optional
from datetime import datetime
from .auth_service import auth_service
import logging

logger = logging.getLogger(__name__)

async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user from session
    Returns None if not authenticated
    """
    
    # Check if user is authenticated
    if not request.session.get("authenticated"):
        return None
    
    # Check session expiration
    session_expires = request.session.get("session_expires")
    if session_expires:
        try:
            expires_dt = datetime.fromisoformat(session_expires)
            if datetime.now() > expires_dt:
                # Session expired
                request.session.clear()
                logger.info("Session expired and cleared")
                return None
        except ValueError:
            # Invalid date format, clear session
            request.session.clear()
            return None
    
    # Get user ID from session
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    # Validate user still exists and is active
    user = await auth_service.authenticate_by_id(user_id)
    if not user:
        # User no longer exists or is inactive
        request.session.clear()
        logger.warning(f"User {user_id} no longer exists or is inactive, session cleared")
        return None
    
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "auth_method": request.session.get("auth_method", "unknown"),
        "session_expires": session_expires
    }

async def require_authentication(request: Request) -> Dict[str, Any]:
    """
    Dependency that requires user authentication
    Redirects to login page if not authenticated
    """
    
    user = await get_current_user(request)
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

async def optional_authentication(request: Request) -> Optional[Dict[str, Any]]:
    """
    Dependency that optionally gets current user
    Does not redirect if not authenticated
    """
    return await get_current_user(request)

class AuthenticationRequired:
    """Class-based dependency for authentication with custom redirect"""
    
    def __init__(self, redirect_url: str = "/login"):
        self.redirect_url = redirect_url
    
    async def __call__(self, request: Request) -> Dict[str, Any]:
        user = await get_current_user(request)
        if not user:
            # Store original URL for redirect after login
            original_url = str(request.url)
            if request.method == "GET":
                request.session["redirect_after_login"] = original_url
            
            return RedirectResponse(url=self.redirect_url, status_code=HTTP_303_SEE_OTHER)
        
        return user
```

## 5. Protecting Existing Routes

### Update Existing Routes with Authentication

Modify your existing routes to require authentication:

```python
from authentication.dependencies import require_authentication, optional_authentication

# Update the country selection route
@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_authentication)
):
    """Serve country selection page - requires authentication"""
    
    # Add current user info to the page
    username = current_user["username"]
    
    # Your existing country selection logic here...
    # Add user info to the template if needed
    
    return f"""
    <!-- Add user info to the top of the page -->
    <div style="text-align: right; padding: 10px; background: #f8f9fa; border-bottom: 1px solid #dee2e6;">
        Welcome, <strong>{username}</strong> | 
        <form method="post" action="/logout" style="display: inline;">
            <button type="submit" style="background: none; border: none; color: #198484; cursor: pointer; text-decoration: underline;">
                Logout
            </button>
        </form>
    </div>
    <!-- Your existing HTML content here -->
    """

# Update the chat interface route
@app.get("/chat/", response_class=HTMLResponse)
async def chat_interface_page(
    request: Request, 
    session_id: str = None,
    current_user: Dict[str, Any] = Depends(require_authentication)
):
    """Serve the chat interface page - requires authentication"""
    
    # Your existing chat interface logic here...
    # Now you can access current_user["user_id"], current_user["username"], etc.
    
    # Update session manager to associate with authenticated user
    session = await session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(404, "Invalid session")
    
    # Associate session with authenticated user if not already
    if not session.get("auth_user_id"):
        # Update the ChatSession in database to link with authenticated user
        # This would require updating your session_manager.py
        pass
    
    # Your existing response logic...

# Update the proceed to chat route
@app.post("/proceed-to-chat")
async def proceed_to_chat(
    request: Request, 
    country: str = Form(...), 
    service_type: str = Form(...),
    current_user: Dict[str, Any] = Depends(require_authentication)
):
    """Handle form submission and redirect to chat interface - requires authentication"""
    
    if not country or not service_type:
        raise HTTPException(status_code=400, detail="Country and service type are required")
    
    # Create session with authenticated user info
    session_id, session_data, is_new = await session_manager.get_or_create_session(
        country=country,
        service_type=service_type,
        user_id=current_user["user_id"]  # Now we have the authenticated user ID
    )
    
    # Your existing logic...
```

## 6. Enhanced Session Manager Integration

### Update Session Manager for Authentication

Add these methods to your `session_manager.py`:

```python
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
                "authentication_method": session.authentication_method
            }
            for session in sessions
        ]
    except Exception as e:
        print(f"Error retrieving user sessions: {e}")
        return []
```

## 7. Error Handling and User Experience

### Create Custom Error Pages

Create `templates/error.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Growbal Intelligence - Error</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* Use similar styling to login.html */
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', Arial, sans-serif;
            background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .error-container {
            max-width: 500px;
            width: 90%;
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1);
            text-align: center;
        }
        .error-icon {
            font-size: 4rem;
            color: #dc3545;
            margin-bottom: 20px;
        }
        .error-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #2b5556;
            margin-bottom: 15px;
        }
        .error-message {
            font-size: 1rem;
            color: #666;
            margin-bottom: 30px;
            line-height: 1.5;
        }
        .btn-primary {
            background: linear-gradient(135deg, #198484 0%, #16a6a6 100%);
            border: none;
            color: white;
            font-weight: 600;
            border-radius: 10px;
            padding: 15px 30px;
            font-size: 16px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(25, 132, 132, 0.3);
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-icon">⚠️</div>
        <h1 class="error-title">{{ title or "An Error Occurred" }}</h1>
        <p class="error-message">{{ message or "Something went wrong. Please try again later." }}</p>
        <a href="/login" class="btn-primary">Return to Login</a>
    </div>
</body>
</html>
```

### Add Error Handling to Routes

```python
from fastapi import HTTPException
from fastapi.exception_handlers import http_exception_handler

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    """Handle 401 Unauthorized errors"""
    return templates.TemplateResponse("error.html", {
        "request": request,
        "title": "Authentication Required",
        "message": "You need to sign in to access this page."
    }, status_code=401)

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    """Handle 403 Forbidden errors"""
    return templates.TemplateResponse("error.html", {
        "request": request,
        "title": "Access Denied",
        "message": "You don't have permission to access this resource."
    }, status_code=403)
```

## 8. Testing the Login System

### Create Login System Test

Create `authentication/test_login_system.py`:

```python
"""
Test the login system integration
"""
import asyncio
from fastapi.testclient import TestClient
from authentication.models import LoginRequest
from authentication.auth_service import auth_service

# You'll need to import your main app
# from main import app

async def test_login_flow():
    """Test the complete login flow"""
    print("🧪 Testing login system integration...")
    
    # Test 1: Test login page accessibility
    print("\n1. Testing login page...")
    # client = TestClient(app)
    # response = client.get("/login")
    # print(f"Login page status: {response.status_code}")
    # print(f"Login page accessible: {'login-form' in response.text}")
    
    # Test 2: Test authentication service directly
    print("\n2. Testing authentication service...")
    
    # Test invalid credentials
    invalid_login = LoginRequest(username="invalid", password="invalid")
    invalid_result = await auth_service.authenticate_user(invalid_login)
    print(f"Invalid credentials rejected: {not invalid_result.success}")
    
    # Test 3: Test form submission (would need test user)
    print("\n3. Testing form submission...")
    print("Note: Requires test user in database for full integration test")
    
    print("\n✅ Login system basic tests completed!")

if __name__ == "__main__":
    asyncio.run(test_login_flow())
```

## 9. Security Enhancements

### CSRF Protection (Optional)

```python
# Add CSRF protection if needed
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
import secrets

def generate_csrf_token():
    """Generate CSRF token"""
    return secrets.token_urlsafe(32)

@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """Basic CSRF protection middleware"""
    
    if request.method in ["POST", "PUT", "DELETE"]:
        # Skip CSRF for API endpoints or add proper CSRF handling
        if not request.url.path.startswith("/api/"):
            # Add CSRF validation logic here if needed
            pass
    
    response = await call_next(request)
    return response
```

### Session Security Configuration

```python
# Add to your session middleware configuration
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production"),
    max_age=None,  # Session cookies (deleted when browser closes)
    same_site="lax",  # CSRF protection
    https_only=True,  # Set to True in production with HTTPS
    domain=None  # Set domain if needed
)
```

## 10. Testing and Validation

### Pre-Phase 4 Checklist

- [ ] Login page renders correctly
- [ ] Form submission handles authentication properly
- [ ] Error messages display correctly
- [ ] Rate limiting works
- [ ] Session creation works
- [ ] Logout functionality works
- [ ] Authentication dependency protects routes
- [ ] Templates are properly configured

### Manual Testing Steps

1. **Test Login Page**:
   ```bash
   # Start your application and visit
   http://localhost:8000/login
   ```

2. **Test Authentication Flow**:
   - Try invalid credentials
   - Try valid credentials (if test user exists)
   - Check session persistence
   - Test logout functionality

3. **Test Protected Routes**:
   - Try accessing `/country/` without authentication
   - Should redirect to login page
   - After login, should redirect back to original page

### Integration Testing

```bash
# Run the login system test
python authentication/test_login_system.py

# Test with curl
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass"
```

## Next Steps

After completing this phase:

1. Verify login page works correctly
2. Test authentication flow with actual users
3. Ensure all existing routes are properly protected
4. Proceed to Phase 4: Session Management Integration
5. Document any UI/UX customizations needed

## Security Reminders

1. **Always use HTTPS in production**
2. **Implement proper CSRF protection**
3. **Use secure session configuration**
4. **Validate all user inputs**
5. **Implement proper rate limiting**
6. **Log security events appropriately**
7. **Test authentication thoroughly**