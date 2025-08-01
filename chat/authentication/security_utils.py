"""
Security utilities for authentication
"""
import hashlib
import secrets
import time
from typing import Dict, List
from collections import defaultdict
from datetime import datetime, timedelta

class SecurityUtils:
    """Security utilities for authentication system"""
    
    def __init__(self):
        self.failed_attempts = defaultdict(list)
        self.blocked_ips = {}
    
    def is_rate_limited(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """
        Check if identifier (IP/email) is rate limited
        
        Args:
            identifier: IP address or email
            max_attempts: Maximum attempts allowed
            window_minutes: Time window in minutes
            
        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.now()
        cutoff = now - timedelta(minutes=window_minutes)
        
        # Clean old attempts
        self.failed_attempts[identifier] = [
            attempt for attempt in self.failed_attempts[identifier]
            if attempt > cutoff
        ]
        
        return len(self.failed_attempts[identifier]) >= max_attempts
    
    def record_failed_attempt(self, identifier: str):
        """Record a failed authentication attempt"""
        self.failed_attempts[identifier].append(datetime.now())
    
    def clear_failed_attempts(self, identifier: str):
        """Clear failed attempts for identifier"""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for logging/storage"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def validate_input_safety(self, input_data: str) -> bool:
        """Basic input validation for security"""
        # Check for common injection patterns
        dangerous_patterns = ['<script', 'javascript:', 'onload=', 'onerror=', 'DROP TABLE', 'UNION SELECT']
        
        input_lower = input_data.lower()
        return not any(pattern.lower() in input_lower for pattern in dangerous_patterns)

# Global security utilities instance
security_utils = SecurityUtils()