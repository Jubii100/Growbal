"""
Main authentication service that combines user lookup and password verification
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from .user_repository import user_repository
from .password_service import password_service
from .models import AuthUser, LoginRequest, AuthenticationResult

logger = logging.getLogger(__name__)

class AuthenticationService:
    """Main service for user authentication operations"""
    
    def __init__(self):
        self.user_repo = user_repository
        self.password_service = password_service
    
    async def authenticate_user(self, login_request: LoginRequest) -> AuthenticationResult:
        """
        Authenticate user with email and password
        
        Args:
            login_request: Login request containing credentials
            
        Returns:
            AuthenticationResult with success status and user data
        """
        try:
            # Normalize email (strip whitespace, convert to lowercase)
            email = login_request.email.strip().lower()
            
            # Find user by email
            user = self.user_repo.get_user_by_email(email)
            
            if not user:
                logger.warning(f"Authentication failed: User not found - {email}")
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid email or password"
                )
            
            # Check if user is active and not deleted
            if not user.is_active or user.is_deleted:
                logger.warning(f"Authentication failed: User inactive/deleted - {email}")
                return AuthenticationResult(
                    success=False,
                    error_message="Account is disabled"
                )
            
            # Verify password
            if not self.password_service.verify_password(login_request.password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password - {email}")
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid email or password"
                )
            
            # Clear password hash from user object for security
            user.password_hash = ""
            
            logger.info(f"Authentication successful - User: {email} (ID: {user.user_id})")
            
            return AuthenticationResult(
                success=True,
                user=user,
                error_message=None
            )
            
        except Exception as e:
            logger.error(f"Authentication error for {login_request.email}: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Authentication service error"
            )
    
    async def authenticate_by_id(self, user_id: int) -> Optional[AuthUser]:
        """
        Authenticate user by ID (for session validation)
        
        Args:
            user_id: User ID to authenticate
            
        Returns:
            AuthUser object or None if not found/inactive
        """
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if user and user.is_active and not user.is_deleted:
                # Clear password hash for security
                user.password_hash = ""
                return user
            return None
            
        except Exception as e:
            logger.error(f"ID authentication error for user {user_id}: {e}")
            return None
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Validate password strength requirements
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        is_valid, issues = self.password_service.validate_password_strength(password)
        
        return {
            'is_valid': is_valid,
            'issues': issues,
            'strength_score': self._calculate_strength_score(password)
        }
    
    def _calculate_strength_score(self, password: str) -> int:
        """
        Calculate password strength score (0-100)
        
        Args:
            password: Password to score
            
        Returns:
            Strength score from 0 to 100
        """
        score = 0
        
        # Length scoring
        if len(password) >= 8:
            score += 20
        if len(password) >= 12:
            score += 10
        if len(password) >= 16:
            score += 10
        
        # Character variety scoring
        if any(c.isupper() for c in password):
            score += 15
        if any(c.islower() for c in password):
            score += 15
        if any(c.isdigit() for c in password):
            score += 15
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 15
        
        return min(score, 100)
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information by ID (for session management)
        
        Args:
            user_id: User ID to retrieve
            
        Returns:
            User information dictionary or None
        """
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if user:
                return user.to_dict()
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving user info for ID {user_id}: {e}")
            return None

# Global authentication service instance
auth_service = AuthenticationService()