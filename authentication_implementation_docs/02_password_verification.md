# Phase 2: Password Verification Implementation

## Overview

This phase implements secure BCrypt password verification for user authentication. The system will verify plaintext passwords against BCrypt hashes stored in the MySQL database.

## Prerequisites

- Phase 1 (Database Setup) completed
- MySQL database with BCrypt-hashed passwords in format `$2a$10$...`
- Understanding of BCrypt cost factors and security implications

## 1. Password Verification Dependencies

### Install BCrypt Library

```bash
pip install bcrypt passlib
```

### Alternative: Using passlib (More Flexible)

```bash
pip install passlib[bcrypt]
```

## 2. Password Service Implementation

### Create Password Verification Service

Create `authentication/password_service.py`:

```python
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
```

## 3. Authentication Service Integration

### Create Authentication Service

Create `authentication/auth_service.py`:

```python
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
        Authenticate user with username/email and password
        
        Args:
            login_request: Login request containing credentials
            
        Returns:
            AuthenticationResult with success status and user data
        """
        try:
            # Normalize username (strip whitespace, convert to lowercase if email)
            username = login_request.username.strip()
            
            # Try to find user by username first, then by email
            user = self.user_repo.get_user_by_username(username)
            if not user and '@' in username:
                # If username looks like email, try email lookup
                user = self.user_repo.get_user_by_email(username)
            
            if not user:
                logger.warning(f"Authentication failed: User not found - {username}")
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Authentication failed: User inactive - {username}")
                return AuthenticationResult(
                    success=False,
                    error_message="Account is disabled"
                )
            
            # Verify password
            if not self.password_service.verify_password(login_request.password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password - {username}")
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            # Update last login timestamp
            self.user_repo.update_last_login(user.user_id)
            
            # Clear password hash from user object for security
            user.password_hash = ""
            user.last_login = datetime.now()
            
            logger.info(f"Authentication successful - User: {username} (ID: {user.user_id})")
            
            return AuthenticationResult(
                success=True,
                user=user,
                error_message=None
            )
            
        except Exception as e:
            logger.error(f"Authentication error for {login_request.username}: {e}")
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
            if user and user.is_active:
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
```

## 4. Password Testing and Validation

### Create Password Testing Script

Create `authentication/test_passwords.py`:

```python
"""
Password verification testing and validation
"""
import asyncio
from .password_service import password_service
from .auth_service import auth_service
from .models import LoginRequest

async def test_password_verification():
    """Test password verification functionality"""
    print("🔐 Testing password verification system...")
    
    # Test 1: BCrypt hash verification
    print("\n1. Testing BCrypt hash verification...")
    
    # Example BCrypt hash (password: "testpassword123")
    test_hash = "$2a$10$N2yN5va.1OjCWEa3dI7zQOoFpLdPZQJJhZHK2y3QJ5xqJ8s2RJNsK"
    test_password = "testpassword123"
    
    result = password_service.verify_password(test_password, test_hash)
    print(f"✅ Password verification: {result}")
    
    # Test with wrong password
    wrong_result = password_service.verify_password("wrongpassword", test_hash)
    print(f"❌ Wrong password verification: {wrong_result}")
    
    # Test 2: Hash information extraction
    print("\n2. Testing hash information extraction...")
    hash_info = password_service.get_hash_info(test_hash)
    print(f"📊 Hash info: {hash_info}")
    
    # Test 3: Password strength validation
    print("\n3. Testing password strength validation...")
    passwords_to_test = [
        "weak",
        "StrongPass123!",
        "VeryWeakPassword",
        "ComplexP@ssw0rd2024!"
    ]
    
    for pwd in passwords_to_test:
        strength = auth_service.validate_password_strength(pwd)
        print(f"Password '{pwd}': Score {strength['strength_score']}/100, Valid: {strength['is_valid']}")
        if not strength['is_valid']:
            print(f"  Issues: {', '.join(strength['issues'])}")
    
    # Test 4: Full authentication flow (if test user exists)
    print("\n4. Testing full authentication flow...")
    
    # Note: Replace with actual test credentials from your database
    test_login = LoginRequest(
        username="testuser",  # Replace with actual username
        password="testpassword123"  # Replace with actual password
    )
    
    auth_result = await auth_service.authenticate_user(test_login)
    
    if auth_result.success:
        print(f"✅ Authentication successful: {auth_result.user.username}")
    else:
        print(f"❌ Authentication failed: {auth_result.error_message}")
    
    print("\n✅ Password verification testing complete!")

async def benchmark_password_verification():
    """Benchmark password verification performance"""
    import time
    
    print("⏱️ Benchmarking password verification performance...")
    
    test_hash = "$2a$10$N2yN5va.1OjCWEa3dI7zQOoFpLdPZQJJhZHK2y3QJ5xqJ8s2RJNsK"
    test_password = "testpassword123"
    
    # Benchmark verification speed
    start_time = time.time()
    iterations = 100
    
    for i in range(iterations):
        password_service.verify_password(test_password, test_hash)
    
    end_time = time.time()
    avg_time = (end_time - start_time) / iterations
    
    print(f"Average verification time: {avg_time*1000:.2f}ms")
    print(f"Verifications per second: {1/avg_time:.0f}")
    
    # Security note about timing
    print("\n🔒 Security Note:")
    print("   BCrypt is intentionally slow to prevent brute force attacks")
    print("   Typical verification time should be 50-100ms")
    print("   Consider implementing rate limiting for login attempts")

if __name__ == "__main__":
    asyncio.run(test_password_verification())
    asyncio.run(benchmark_password_verification())
```

## 5. Security Considerations and Best Practices

### Password Security Guidelines

```python
"""
Password security configuration and guidelines
"""

# Security Configuration
PASSWORD_SECURITY_CONFIG = {
    # BCrypt settings
    'bcrypt_rounds': 12,  # Higher cost for better security (10-12 recommended)
    'max_verification_time_ms': 200,  # Maximum acceptable verification time
    
    # Password requirements
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_digits': True,
    'require_special_chars': True,
    
    # Security policies
    'max_login_attempts': 5,
    'lockout_duration_minutes': 15,
    'password_history_count': 5,  # Remember last N passwords
    
    # Logging and monitoring
    'log_failed_attempts': True,
    'log_successful_logins': True,
    'alert_on_multiple_failures': True
}

# Common weak passwords to reject
COMMON_WEAK_PASSWORDS = {
    'password', 'password123', '123456', 'qwerty', 'admin', 
    'letmein', 'welcome', 'monkey', '1234567890', 'abc123'
}
```

### Security Implementation

Create `authentication/security_utils.py`:

```python
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
        Check if identifier (IP/username) is rate limited
        
        Args:
            identifier: IP address or username
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
```

## 6. Integration Testing

### Create Integration Test Script

Create `authentication/integration_test.py`:

```python
"""
Integration testing for authentication system
"""
import asyncio
import json
from .auth_service import auth_service
from .password_service import password_service
from .user_repository import user_repository
from .models import LoginRequest

async def run_integration_tests():
    """Run comprehensive integration tests"""
    print("🧪 Running authentication integration tests...")
    
    test_results = []
    
    # Test 1: Database connectivity
    print("\n1. Testing database connectivity...")
    try:
        structure = user_repository.verify_database_structure()
        if structure["connection_status"] == "success":
            test_results.append(("Database Connectivity", "✅ PASS"))
            print(f"   Connected to database with {structure['total_users']} users")
        else:
            test_results.append(("Database Connectivity", "❌ FAIL"))
            print(f"   Database connection failed: {structure.get('error')}")
    except Exception as e:
        test_results.append(("Database Connectivity", f"❌ FAIL - {e}"))
    
    # Test 2: Password service functionality
    print("\n2. Testing password service...")
    try:
        # Test password hashing
        test_password = "TestPassword123!"
        hashed = password_service.hash_password(test_password)
        
        # Test verification
        verify_correct = password_service.verify_password(test_password, hashed)
        verify_incorrect = password_service.verify_password("WrongPassword", hashed)
        
        if verify_correct and not verify_incorrect:
            test_results.append(("Password Service", "✅ PASS"))
            print("   Password hashing and verification working correctly")
        else:
            test_results.append(("Password Service", "❌ FAIL"))
            print("   Password verification not working correctly")
    except Exception as e:
        test_results.append(("Password Service", f"❌ FAIL - {e}"))
    
    # Test 3: Authentication service (requires test user)
    print("\n3. Testing authentication service...")
    try:
        # Test with invalid credentials
        invalid_login = LoginRequest(username="nonexistent", password="invalid")
        invalid_result = await auth_service.authenticate_user(invalid_login)
        
        if not invalid_result.success:
            test_results.append(("Authentication - Invalid User", "✅ PASS"))
            print("   Invalid user correctly rejected")
        else:
            test_results.append(("Authentication - Invalid User", "❌ FAIL"))
            print("   Invalid user incorrectly accepted")
        
        # Test password strength validation
        strength_test = auth_service.validate_password_strength("WeakPass")
        if not strength_test['is_valid']:
            test_results.append(("Password Strength Validation", "✅ PASS"))
            print("   Weak password correctly rejected")
        else:
            test_results.append(("Password Strength Validation", "❌ FAIL"))
            print("   Weak password incorrectly accepted")
            
    except Exception as e:
        test_results.append(("Authentication Service", f"❌ FAIL - {e}"))
    
    # Print test summary
    print("\n" + "="*50)
    print("TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        print(f"{test_name}: {result}")
        if "PASS" in result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal Tests: {len(test_results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Authentication system is ready.")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please review and fix issues.")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    exit(0 if success else 1)
```

## 7. Configuration and Deployment

### Environment Configuration

Add to your `.env` file:

```bash
# Password Security Configuration
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_DIGITS=true
PASSWORD_REQUIRE_SPECIAL=true

# Authentication Rate Limiting
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15

# BCrypt Configuration
BCRYPT_ROUNDS=12

# Security Logging
LOG_FAILED_LOGINS=true
LOG_SUCCESSFUL_LOGINS=true
```

### Logging Configuration

Add to your logging configuration:

```python
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '[{asctime}] SECURITY {levelname}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/security.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'security',
        },
    },
    'loggers': {
        'authentication': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

## 8. Testing and Validation

### Pre-Phase 3 Checklist

- [ ] Password verification works with BCrypt hashes
- [ ] Authentication service handles invalid credentials properly
- [ ] Password strength validation is working
- [ ] Rate limiting is implemented
- [ ] Security logging is configured
- [ ] Integration tests pass successfully

### Manual Testing Commands

```bash
# Test password verification
python -c "
from authentication.password_service import password_service
result = password_service.verify_password('test123', '$2a$10$...')
print('Password verification:', result)
"

# Run integration tests
python authentication/integration_test.py

# Test password strength
python -c "
from authentication.auth_service import auth_service
result = auth_service.validate_password_strength('TestPass123!')
print('Password strength:', result)
"
```

## Next Steps

After completing this phase:

1. Verify all password verification functionality is working
2. Test with actual user credentials from your database
3. Run the integration test suite
4. Proceed to Phase 3: Login System Implementation
5. Document any customizations needed for your specific hash format

## Security Reminders

1. **Never log passwords or password hashes**
2. **Always use HTTPS in production**
3. **Implement proper rate limiting**
4. **Monitor authentication attempts**
5. **Regularly update BCrypt cost factors**
6. **Use secure random number generation**
7. **Implement proper error handling**