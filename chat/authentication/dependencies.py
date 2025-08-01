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
        "email": user.email,
        "full_name": user.full_name,
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
        raise HTTPException(
            status_code=HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    
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
            
            raise HTTPException(
                status_code=HTTP_303_SEE_OTHER,
                headers={"Location": self.redirect_url}
            )
        
        return user