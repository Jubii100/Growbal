"""
Authentication routes for FastAPI application
"""
import os
import logging
from datetime import datetime, timedelta
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER
from .auth_service import auth_service
from .models import LoginRequest
from .security_utils import security_utils

logger = logging.getLogger(__name__)

# Setup templates directory
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

async def login_page(request: Request, error: str = None, success: str = None):
    """Serve the login page"""
    
    # Check if user is already authenticated
    if request.session.get("authenticated"):
        # Redirect to original destination or country selection
        redirect_url = request.session.get("redirect_after_login", "/country/")
        return RedirectResponse(url=redirect_url, status_code=HTTP_303_SEE_OTHER)
    
    # Read logo file if exists
    logo_html = ""
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "growbal_logoheader.svg")
    if os.path.exists(logo_path):
        with open(logo_path, 'r') as f:
            logo_content = f.read()
            logo_html = f"""
            <div style="max-width: 150px; height: auto; margin: 0 auto;">
                {logo_content}
            </div>
            """
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "success": success,
        "logo_html": logo_html
    })

async def process_login(
    request: Request,
    email: str = Form(...),
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
            "email": email
        })
    
    # Validate input
    if not security_utils.validate_input_safety(email) or not security_utils.validate_input_safety(password):
        security_utils.record_failed_attempt(client_ip)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid input detected.",
            "email": email
        })
    
    # Create login request with email
    login_request = LoginRequest(
        email=email.strip().lower(),
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
            request.session["auth_user_id"] = auth_result.user.user_id
            request.session["email"] = auth_result.user.email
            request.session["full_name"] = auth_result.user.full_name
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
            logger.info(f"Successful login: {email} from {client_ip}")
            
            # Redirect to original destination or country selection
            redirect_url = request.session.get("redirect_after_login", "/country/")
            request.session.pop("redirect_after_login", None)
            
            return RedirectResponse(url=redirect_url, status_code=HTTP_303_SEE_OTHER)
        
        else:
            # Record failed attempt
            security_utils.record_failed_attempt(client_ip)
            
            # Log failed attempt
            logger.warning(f"Failed login attempt: {email} from {client_ip}")
            
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": auth_result.error_message,
                "email": email
            })
    
    except Exception as e:
        # Record failed attempt
        security_utils.record_failed_attempt(client_ip)
        
        # Log error
        logger.error(f"Login error for {email}: {e}")
        
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Login service temporarily unavailable. Please try again later.",
            "email": email
        })

async def logout(request: Request):
    """Handle user logout"""
    
    # Log logout
    email = request.session.get("email", "unknown")
    logger.info(f"User logout: {email}")
    
    # Clear session
    request.session.clear()
    
    # Redirect to login page with success message
    return RedirectResponse(
        url="/login?success=You have been successfully logged out.",
        status_code=HTTP_303_SEE_OTHER
    )