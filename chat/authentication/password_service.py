"""
Password verification service using BCrypt
"""
import bcrypt
import logging
from typing import Optional, Tuple
from passlib.context import CryptContext
from passlib.hash import bcrypt as passlib_bcrypt

logger = logging.getLogger(__name__)

class PasswordService:
    """Service for password verification and hashing operations"""
    
    def __init__(self):
        # Initialize passlib CryptContext for flexibility
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__default_rounds=12  # Higher security for new passwords
        )
    
    def verify_password_bcrypt(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password using direct bcrypt library
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: BCrypt hash from database (e.g., $2a$10$...)
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            # Convert strings to bytes
            plain_bytes = plain_password.encode('utf-8')
            hash_bytes = hashed_password.encode('utf-8')
            
            # Verify using bcrypt
            result = bcrypt.checkpw(plain_bytes, hash_bytes)
            
            logger.info(f"Password verification result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def verify_password_passlib(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password using passlib (supports multiple hash formats)
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: Hash from database
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            result = self.pwd_context.verify(plain_password, hashed_password)
            logger.info(f"Password verification (passlib) result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Password verification (passlib) error: {e}")
            return False
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Main password verification method (uses bcrypt by default)
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: Hash from database
            
        Returns:
            True if password matches, False otherwise
        """
        if not plain_password or not hashed_password:
            logger.warning("Empty password or hash provided")
            return False
        
        # Check if it's a BCrypt hash
        if hashed_password.startswith(('$2a$', '$2b$', '$2x$', '$2y$')):
            return self.verify_password_bcrypt(plain_password, hashed_password)
        else:
            # Try passlib for other hash formats
            return self.verify_password_passlib(plain_password, hashed_password)
    
    def hash_password(self, plain_password: str) -> str:
        """
        Hash a password using BCrypt (for creating new passwords)
        
        Args:
            plain_password: Plaintext password to hash
            
        Returns:
            BCrypt hash string
        """
        try:
            # Generate salt and hash
            salt = bcrypt.gensalt(rounds=12)  # Higher cost for better security
            hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            raise ValueError(f"Failed to hash password: {e}")
    
    def get_hash_info(self, hashed_password: str) -> dict:
        """
        Extract information from a password hash
        
        Args:
            hashed_password: Hash to analyze
            
        Returns:
            Dictionary with hash information
        """
        try:
            if hashed_password.startswith('$2a$'):
                parts = hashed_password.split('$')
                if len(parts) >= 4:
                    return {
                        'algorithm': 'bcrypt',
                        'variant': parts[1],
                        'cost': int(parts[2]),
                        'salt': parts[3][:22] if len(parts[3]) >= 22 else parts[3],
                        'hash_length': len(hashed_password),
                        'is_valid_format': True
                    }
            
            return {
                'algorithm': 'unknown',
                'is_valid_format': False,
                'hash_length': len(hashed_password)
            }
            
        except Exception as e:
            logger.error(f"Hash analysis error: {e}")
            return {'error': str(e), 'is_valid_format': False}
    
    def validate_password_strength(self, password: str) -> Tuple[bool, list]:
        """
        Validate password strength
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Password must contain at least one special character")
        
        return len(issues) == 0, issues

# Global service instance
password_service = PasswordService()