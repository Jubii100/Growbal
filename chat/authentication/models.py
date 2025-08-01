"""
Authentication models and user data structures
Adapted for the existing Growbal user table schema
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class AuthUser:
    """Represents a user from the authentication database - adapted for Growbal schema"""
    user_id: int
    email: Optional[str]
    full_name: Optional[str]
    password_hash: str
    phone: Optional[str]
    role: Optional[int]
    is_active: bool = True
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    confirm_email: bool = False
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage"""
        return {
            'user_id': self.user_id,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'is_active': self.is_active,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'provider': self.provider,
            'provider_id': self.provider_id,
            'confirm_email': self.confirm_email,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthUser':
        """Create from dictionary (for session retrieval)"""
        return cls(
            user_id=data['user_id'],
            email=data.get('email'),
            full_name=data.get('full_name'),
            password_hash='',  # Never store password hash in session
            phone=data.get('phone'),
            role=data.get('role'),
            is_active=data.get('is_active', True),
            is_deleted=data.get('is_deleted', False),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            provider=data.get('provider'),
            provider_id=data.get('provider_id'),
            confirm_email=data.get('confirm_email', False),
            metadata=data.get('metadata', {})
        )
    
    @property 
    def display_name(self) -> str:
        """Get display name for the user"""
        return self.full_name or self.email or f"User {self.user_id}"
    
    @property
    def username(self) -> str:
        """Compatibility property - returns email as username"""
        return self.email or f"user_{self.user_id}"

@dataclass
class LoginRequest:
    """Login request data structure"""
    email: str  # Using email instead of username
    password: str
    remember_me: bool = False

@dataclass
class AuthenticationResult:
    """Authentication result with user data and session info"""
    success: bool
    user: Optional[AuthUser] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None