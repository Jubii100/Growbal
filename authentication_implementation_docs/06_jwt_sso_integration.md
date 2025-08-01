# Phase 6: JWT SSO Integration

## Overview

This phase implements JWT-based Single Sign-On (SSO) integration with partner sites. Users authenticated on partner websites can seamlessly access the FastAPI application without re-entering credentials through secure JWT token verification.

## Prerequisites

- Phase 1-5 completed successfully
- Understanding of JWT tokens and digital signatures
- Coordination with partner sites for token format and signing keys
- HTTPS communication between partner sites and FastAPI app

## 1. JWT SSO Dependencies

### Install JWT Dependencies

```bash
pip install PyJWT cryptography
```

## 2. JWT Configuration and Key Management

### Create JWT Configuration

Create `authentication/jwt_config.py`:

```python
"""
JWT SSO Configuration and Key Management
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.hashes import SHA256

logger = logging.getLogger(__name__)

class JWTConfig:
    """JWT configuration for SSO integration"""
    
    # Supported algorithms
    SUPPORTED_ALGORITHMS = ["HS256", "HS512", "RS256", "RS512"]
    
    # Default token expiration (5 minutes for security)
    DEFAULT_TOKEN_EXPIRATION = 300  # 5 minutes
    
    # Partner configurations
    PARTNER_CONFIGS = {
        "partner1": {
            "name": "Partner Site 1",
            "algorithm": "HS256",
            "secret": os.getenv("PARTNER1_JWT_SECRET"),
            "issuer": "partner1.com",
            "audience": "growbal.ai",
            "max_token_age": 300,  # 5 minutes
            "trusted": True
        },
        "partner2": {
            "name": "Partner Site 2", 
            "algorithm": "RS256",
            "public_key_path": os.getenv("PARTNER2_PUBLIC_KEY_PATH"),
            "issuer": "partner2.com",
            "audience": "growbal.ai",
            "max_token_age": 600,  # 10 minutes
            "trusted": True
        }
    }
    
    @classmethod
    def get_partner_config(cls, partner_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific partner"""
        return cls.PARTNER_CONFIGS.get(partner_id)
    
    @classmethod
    def load_public_key(cls, key_path: str) -> Optional[str]:
        """Load RSA public key from file"""
        try:
            if not os.path.exists(key_path):
                logger.error(f"Public key file not found: {key_path}")
                return None
            
            with open(key_path, 'rb') as key_file:
                public_key = serialization.load_pem_public_key(key_file.read())
                
            # Convert to PEM format string
            pem_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return pem_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error loading public key {key_path}: {e}")
            return None
    
    @classmethod
    def validate_partner_config(cls, partner_id: str) -> bool:
        """Validate partner configuration"""
        config = cls.get_partner_config(partner_id)
        if not config:
            return False
        
        # Check required fields
        required_fields = ["algorithm", "issuer", "audience"]
        for field in required_fields:
            if not config.get(field):
                logger.error(f"Missing required field '{field}' for partner {partner_id}")
                return False
        
        # Validate algorithm support
        if config["algorithm"] not in cls.SUPPORTED_ALGORITHMS:
            logger.error(f"Unsupported algorithm '{config['algorithm']}' for partner {partner_id}")
            return False
        
        # Validate signing key/secret
        if config["algorithm"].startswith("HS"):
            # HMAC algorithms need secret
            if not config.get("secret"):
                logger.error(f"Missing secret for HMAC algorithm in partner {partner_id}")
                return False
        elif config["algorithm"].startswith("RS"):
            # RSA algorithms need public key
            if not config.get("public_key_path"):
                logger.error(f"Missing public key path for RSA algorithm in partner {partner_id}")
                return False
            
            # Try to load the key
            key_content = cls.load_public_key(config["public_key_path"])
            if not key_content:
                return False
        
        return True
    
    @classmethod
    def get_all_valid_partners(cls) -> Dict[str, Dict[str, Any]]:
        """Get all partners with valid configurations"""
        valid_partners = {}
        
        for partner_id, config in cls.PARTNER_CONFIGS.items():
            if cls.validate_partner_config(partner_id):
                valid_partners[partner_id] = config
        
        return valid_partners
```

### Environment Configuration

Add to your `.env` file:

```bash
# JWT SSO Configuration
PARTNER1_JWT_SECRET=your-shared-secret-with-partner1-must-be-complex
PARTNER2_PUBLIC_KEY_PATH=/path/to/partner2/public_key.pem

# SSO Security Settings
SSO_TOKEN_MAX_AGE=300
SSO_REQUIRE_HTTPS=true
SSO_LOG_ALL_ATTEMPTS=true
SSO_ENABLE_PARTNER_VALIDATION=true
```

## 3. JWT Token Verification Service

### Create JWT Service

Create `authentication/jwt_service.py`:

```python
"""
JWT Token Verification Service for SSO
"""
import jwt
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from .jwt_config import JWTConfig
from .models import AuthUser

logger = logging.getLogger(__name__)

class JWTSSOService:
    """Service for JWT-based SSO token verification"""
    
    def __init__(self):
        self.config = JWTConfig()
    
    def verify_sso_token(
        self,
        token: str,
        partner_id: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Verify JWT SSO token
        
        Args:
            token: JWT token to verify
            partner_id: Optional partner ID for specific validation
            
        Returns:
            Tuple of (success, payload, error_message)
        """
        try:
            # Decode token header to identify algorithm and partner
            unverified_header = jwt.get_unverified_header(token)
            algorithm = unverified_header.get("alg")
            
            if algorithm not in JWTConfig.SUPPORTED_ALGORITHMS:
                return False, None, f"Unsupported algorithm: {algorithm}"
            
            # If partner_id not provided, try to determine from token
            if not partner_id:
                # Decode without verification to get issuer
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                issuer = unverified_payload.get("iss")
                
                # Find partner by issuer
                partner_id = self._find_partner_by_issuer(issuer)
                if not partner_id:
                    return False, None, f"Unknown issuer: {issuer}"
            
            # Get partner configuration
            partner_config = JWTConfig.get_partner_config(partner_id)
            if not partner_config:
                return False, None, f"Partner configuration not found: {partner_id}"
            
            if not partner_config.get("trusted"):
                return False, None, f"Partner not trusted: {partner_id}"
            
            # Verify token
            payload = self._verify_token_with_config(token, partner_config)
            if not payload:
                return False, None, "Token verification failed"
            
            # Additional security validations
            validation_result = self._validate_token_claims(payload, partner_config)
            if not validation_result[0]:
                return False, None, validation_result[1]
            
            logger.info(f"Successfully verified SSO token from partner {partner_id}")
            return True, payload, None
            
        except jwt.ExpiredSignatureError:
            logger.warning(f"Expired SSO token from partner {partner_id}")
            return False, None, "Token has expired"
        
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid SSO token from partner {partner_id}: {e}")
            return False, None, "Invalid token format or signature"
        
        except Exception as e:
            logger.error(f"SSO token verification error: {e}")
            return False, None, "Token verification failed"
    
    def _find_partner_by_issuer(self, issuer: str) -> Optional[str]:
        """Find partner ID by token issuer"""
        for partner_id, config in JWTConfig.PARTNER_CONFIGS.items():
            if config.get("issuer") == issuer:
                return partner_id
        return None
    
    def _verify_token_with_config(
        self,
        token: str,
        partner_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Verify token using partner-specific configuration"""
        
        algorithm = partner_config["algorithm"]
        
        try:
            if algorithm.startswith("HS"):
                # HMAC verification
                secret = partner_config["secret"]
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=[algorithm],
                    audience=partner_config["audience"],
                    issuer=partner_config["issuer"]
                )
                
            elif algorithm.startswith("RS"):
                # RSA verification
                public_key_path = partner_config["public_key_path"]
                public_key = JWTConfig.load_public_key(public_key_path)
                
                if not public_key:
                    logger.error(f"Could not load public key: {public_key_path}")
                    return None
                
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=[algorithm],
                    audience=partner_config["audience"],
                    issuer=partner_config["issuer"]
                )
            
            else:
                logger.error(f"Unsupported algorithm: {algorithm}")
                return None
            
            return payload
            
        except Exception as e:
            logger.error(f"Token verification error with config: {e}")
            return None
    
    def _validate_token_claims(
        self,
        payload: Dict[str, Any],
        partner_config: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate token claims for security"""
        
        # Check required claims
        required_claims = ["sub", "iss", "aud", "exp", "iat"]
        for claim in required_claims:
            if claim not in payload:
                return False, f"Missing required claim: {claim}"
        
        # Validate token age
        issued_at = payload.get("iat")
        max_age = partner_config.get("max_token_age", JWTConfig.DEFAULT_TOKEN_EXPIRATION)
        
        if issued_at:
            token_age = datetime.now(timezone.utc).timestamp() - issued_at
            if token_age > max_age:
                return False, f"Token too old: {token_age}s > {max_age}s"
        
        # Validate custom claims if needed
        user_id = payload.get("sub")
        if not user_id:
            return False, "Missing user identifier in token"
        
        # Check for suspicious patterns
        if self._is_suspicious_token(payload):
            return False, "Token contains suspicious patterns"
        
        return True, None
    
    def _is_suspicious_token(self, payload: Dict[str, Any]) -> bool:
        """Check for suspicious token patterns"""
        
        # Check for obviously fake user IDs
        user_id = str(payload.get("sub", ""))
        suspicious_patterns = ["test", "admin", "root", "demo", "guest"]
        
        if any(pattern in user_id.lower() for pattern in suspicious_patterns):
            logger.warning(f"Suspicious user ID in token: {user_id}")
            return True
        
        # Check for unrealistic expiration times
        exp = payload.get("exp", 0)
        iat = payload.get("iat", 0)
        
        if exp - iat > 3600:  # Token valid for more than 1 hour
            logger.warning(f"Token with excessive validity period: {exp - iat}s")
            return True
        
        return False
    
    def extract_user_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user information from verified JWT payload"""
        
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username") or payload.get("preferred_username") or payload.get("sub"),
            "email": payload.get("email"),
            "full_name": payload.get("name"),
            "partner_id": self._find_partner_by_issuer(payload.get("iss")),
            "token_issued_at": payload.get("iat"),
            "token_expires_at": payload.get("exp"),
            "additional_claims": {
                k: v for k, v in payload.items()
                if k not in ["sub", "username", "email", "name", "iss", "aud", "exp", "iat", "nbf"]
            }
        }
    
    def generate_test_token(self, partner_id: str, user_data: Dict[str, Any]) -> Optional[str]:
        """
        Generate test JWT token for development/testing
        WARNING: Only use in development!
        """
        
        if os.getenv("ENVIRONMENT") == "production":
            logger.error("Cannot generate test tokens in production")
            return None
        
        partner_config = JWTConfig.get_partner_config(partner_id)
        if not partner_config:
            return None
        
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_data.get("user_id", "test_user")),
            "username": user_data.get("username", "testuser"),
            "email": user_data.get("email", "test@example.com"),
            "name": user_data.get("full_name", "Test User"),
            "iss": partner_config["issuer"],
            "aud": partner_config["audience"],
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp())
        }
        
        try:
            if partner_config["algorithm"].startswith("HS"):
                token = jwt.encode(payload, partner_config["secret"], algorithm=partner_config["algorithm"])
            else:
                # For RS algorithms, you'd need the private key (not recommended for testing)
                logger.error("Cannot generate RS256 test tokens without private key")
                return None
            
            return token
            
        except Exception as e:
            logger.error(f"Error generating test token: {e}")
            return None

# Global JWT service instance
jwt_sso_service = JWTSSOService()
```

## 4. SSO Authentication Endpoints

### Create SSO Endpoints

Add these routes to your main application or create `authentication/sso_routes.py`:

```python
"""
SSO Authentication Routes
"""
from fastapi import APIRouter, Request, Query, Header, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.status import HTTP_303_SEE_OTHER, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta

from .jwt_service import jwt_sso_service
from .auth_service import auth_service
from .security_utils import security_utils
from chat.session_manager import session_manager

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

sso_router = APIRouter(prefix="/sso", tags=["SSO Authentication"])

@sso_router.get("/login")
async def sso_login_endpoint(
    request: Request,
    token: Optional[str] = Query(None, description="JWT token from partner site"),
    partner: Optional[str] = Query(None, description="Partner identifier"),
    redirect_to: Optional[str] = Query(None, description="URL to redirect after successful login"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    SSO login endpoint for partner site integration
    
    Supports token via:
    - Query parameter: /sso/login?token=<jwt>&partner=<partner_id>
    - Authorization header: Authorization: Bearer <jwt>
    """
    
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")
    
    logger.info(f"SSO login attempt from {client_ip}, partner: {partner}")
    
    # Rate limiting
    if security_utils.is_rate_limited(client_ip, max_attempts=10, window_minutes=5):
        logger.warning(f"SSO rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Too many SSO attempts. Please try again later."
        )
    
    # Get token from query parameter or Authorization header
    jwt_token = token
    if not jwt_token and credentials:
        jwt_token = credentials.credentials
    
    if not jwt_token:
        logger.warning(f"SSO login attempt without token from {client_ip}")
        security_utils.record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="JWT token is required for SSO login"
        )
    
    try:
        # Verify JWT token
        success, payload, error_message = jwt_sso_service.verify_sso_token(jwt_token, partner)
        
        if not success:
            logger.warning(f"SSO token verification failed from {client_ip}: {error_message}")
            security_utils.record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail=f"SSO authentication failed: {error_message}"
            )
        
        # Extract user information from token
        user_info = jwt_sso_service.extract_user_info(payload)
        external_user_id = user_info["user_id"]
        username = user_info["username"]
        email = user_info["email"]
        partner_id = user_info["partner_id"]
        
        logger.info(f"SSO token verified for user {username} from partner {partner_id}")
        
        # Try to find user in authentication database
        auth_user = None
        if email:
            auth_user = await auth_service.auth_service.user_repo.get_user_by_email(email)
        
        if not auth_user and username:
            auth_user = await auth_service.auth_service.user_repo.get_user_by_username(username)
        
        if not auth_user:
            # User not found in our system - handle based on your business logic
            logger.info(f"SSO user {username} not found in local database")
            
            # Option 1: Reject unknown users
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="User not found in system. Please contact administrator."
            )
            
            # Option 2: Auto-create users (uncomment if desired)
            # auth_user = await auto_create_sso_user(user_info)
        
        if not auth_user.is_active:
            logger.warning(f"SSO attempt for inactive user {username}")
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        # Update last login timestamp
        auth_service.auth_service.user_repo.update_last_login(auth_user.user_id)
        
        # Clear any failed attempts
        security_utils.clear_failed_attempts(client_ip)
        
        # Check for existing chat session to associate
        existing_session_id = request.session.get("session_id")
        chat_session_id = None
        session_token = None
        
        if existing_session_id:
            # Associate existing session with authenticated user
            success = await session_manager.associate_session_with_user(
                session_id=existing_session_id,
                user_id=auth_user.user_id,
                username=auth_user.username,
                auth_method="sso"
            )
            
            if success:
                chat_session_id = existing_session_id
                session_data = await session_manager.get_session(existing_session_id)
                session_token = session_data.get("session_token") if session_data else None
        
        # Store authentication info in FastAPI session
        request.session["authenticated"] = True
        request.session["user_id"] = auth_user.user_id
        request.session["username"] = auth_user.username
        request.session["auth_method"] = "sso"
        request.session["sso_partner"] = partner_id
        request.session["login_ip"] = client_ip
        
        if chat_session_id:
            request.session["chat_session_id"] = chat_session_id
            request.session["session_token"] = session_token
        
        # Set session expiration (shorter for SSO)
        request.session["session_expires"] = (
            datetime.now() + timedelta(hours=4)  # 4-hour sessions for SSO
        ).isoformat()
        
        logger.info(f"SSO login successful for {username} from partner {partner_id}")
        
        # Determine redirect URL
        redirect_url = redirect_to or request.session.get("redirect_after_login", "/country/")
        request.session.pop("redirect_after_login", None)
        
        # Security: Validate redirect URL to prevent open redirects
        if not _is_safe_redirect_url(redirect_url, request):
            redirect_url = "/country/"
        
        return RedirectResponse(url=redirect_url, status_code=HTTP_303_SEE_OTHER)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"SSO login error for {client_ip}: {e}")
        security_utils.record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=500,
            detail="SSO authentication service error"
        )

@sso_router.post("/logout")
async def sso_logout_endpoint(request: Request):
    """SSO logout endpoint"""
    
    username = request.session.get("username", "unknown")
    partner = request.session.get("sso_partner", "unknown")
    
    logger.info(f"SSO logout for user {username} from partner {partner}")
    
    # Clear session
    request.session.clear()
    
    return JSONResponse({
        "message": "SSO logout successful",
        "redirect_url": "/login"
    })

@sso_router.get("/verify-token")
async def verify_sso_token_endpoint(
    token: str = Query(..., description="JWT token to verify"),
    partner: Optional[str] = Query(None, description="Partner identifier")
):
    """
    Endpoint to verify JWT token validity (for partner integration testing)
    """
    
    success, payload, error_message = jwt_sso_service.verify_sso_token(token, partner)
    
    if success:
        user_info = jwt_sso_service.extract_user_info(payload)
        return {
            "valid": True,
            "user_info": user_info,
            "expires_at": datetime.fromtimestamp(payload["exp"]).isoformat()
        }
    else:
        return {
            "valid": False,
            "error": error_message
        }

@sso_router.get("/partners")
async def list_sso_partners():
    """List configured SSO partners (for documentation/integration)"""
    
    from .jwt_config import JWTConfig
    
    partners = {}
    for partner_id, config in JWTConfig.get_all_valid_partners().items():
        partners[partner_id] = {
            "name": config["name"],
            "issuer": config["issuer"],
            "audience": config["audience"],
            "algorithm": config["algorithm"],
            "max_token_age": config["max_token_age"]
        }
    
    return {
        "partners": partners,
        "sso_endpoint": "/sso/login",
        "supported_methods": ["query_parameter", "authorization_header"]
    }

def _is_safe_redirect_url(url: str, request: Request) -> bool:
    """Validate redirect URL to prevent open redirect attacks"""
    
    # Allow relative URLs
    if url.startswith("/"):
        return True
    
    # Allow same-origin URLs
    request_host = request.headers.get("host", "")
    if url.startswith(f"https://{request_host}") or url.startswith(f"http://{request_host}"):
        return True
    
    # Reject external URLs
    return False

# Add router to main application:
# app.include_router(sso_router)
```

## 5. Partner Integration Examples

### Create Partner Integration Guide

Create `authentication/partner_integration_examples.py`:

```python
"""
Examples and utilities for partner site integration
"""
import jwt
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

class PartnerIntegrationExamples:
    """Examples for partner site integration"""
    
    @staticmethod
    def generate_redirect_url_example():
        """Example of how partner sites should redirect to SSO endpoint"""
        
        # Example JWT payload that partner should create
        example_payload = {
            "sub": "12345",  # User ID in partner system
            "username": "john.doe",
            "email": "john.doe@partner.com",
            "name": "John Doe",
            "iss": "partner1.com",  # Partner's domain
            "aud": "growbal.ai",    # Your application
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "nbf": int(datetime.now(timezone.utc).timestamp())
        }
        
        # Partner would sign this with their secret
        # token = jwt.encode(example_payload, "partner_secret", algorithm="HS256")
        
        redirect_examples = {
            "query_parameter": "https://growbal.ai/sso/login?token=<JWT_TOKEN>&partner=partner1",
            "with_redirect": "https://growbal.ai/sso/login?token=<JWT_TOKEN>&partner=partner1&redirect_to=/dashboard",
            "payload_example": example_payload
        }
        
        return redirect_examples
    
    @staticmethod
    def javascript_integration_example():
        """JavaScript example for partner sites"""
        
        js_code = """
        // Example JavaScript for partner site integration
        
        // 1. Generate JWT token on partner backend (server-side)
        // This should be done on your server, not in JavaScript
        
        // 2. Redirect user to Growbal with token
        function redirectToGrowbal(jwtToken, redirectUrl = null) {
            const baseUrl = 'https://growbal.ai/sso/login';
            const params = new URLSearchParams({
                token: jwtToken,
                partner: 'partner1'
            });
            
            if (redirectUrl) {
                params.append('redirect_to', redirectUrl);
            }
            
            window.location.href = `${baseUrl}?${params.toString()}`;
        }
        
        // 3. Alternative: Post JWT token in form
        function postToGrowbal(jwtToken) {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = 'https://growbal.ai/sso/login';
            
            const tokenInput = document.createElement('input');
            tokenInput.type = 'hidden';
            tokenInput.name = 'token';
            tokenInput.value = jwtToken;
            
            const partnerInput = document.createElement('input');
            partnerInput.type = 'hidden';
            partnerInput.name = 'partner';
            partnerInput.value = 'partner1';
            
            form.appendChild(tokenInput);
            form.appendChild(partnerInput);
            document.body.appendChild(form);
            form.submit();
        }
        
        // 4. Example usage
        // Assuming you have a JWT token from your backend
        document.getElementById('growbal-login-btn').addEventListener('click', function() {
            // Get JWT token from your backend API
            fetch('/api/generate-growbal-token', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(response => response.json())
            .then(data => {
                if (data.jwt_token) {
                    redirectToGrowbal(data.jwt_token, '/dashboard');
                }
            })
            .catch(error => {
                console.error('Error getting SSO token:', error);
            });
        });
        """
        
        return js_code
    
    @staticmethod
    def php_backend_example():
        """PHP backend example for generating JWT tokens"""
        
        php_code = '''
        <?php
        // Example PHP code for partner backend to generate JWT tokens
        
        require_once 'vendor/autoload.php';
        use Firebase\JWT\JWT;
        use Firebase\JWT\Key;
        
        class GrowbalSSOIntegration {
            private $secret;
            private $algorithm;
            private $issuer;
            private $audience;
            
            public function __construct() {
                $this->secret = 'your-shared-secret-with-growbal';
                $this->algorithm = 'HS256';
                $this->issuer = 'partner1.com';
                $this->audience = 'growbal.ai';
            }
            
            public function generateSSOToken($userId, $username, $email, $fullName = null) {
                $now = time();
                
                $payload = [
                    'sub' => strval($userId),
                    'username' => $username,
                    'email' => $email,
                    'name' => $fullName ?: $username,
                    'iss' => $this->issuer,
                    'aud' => $this->audience,
                    'exp' => $now + 300, // 5 minutes
                    'iat' => $now,
                    'nbf' => $now
                ];
                
                return JWT::encode($payload, $this->secret, $this->algorithm);
            }
            
            public function createGrowbalRedirectUrl($userId, $username, $email, $redirectTo = null) {
                $token = $this->generateSSOToken($userId, $username, $email);
                
                $params = [
                    'token' => $token,
                    'partner' => 'partner1'
                ];
                
                if ($redirectTo) {
                    $params['redirect_to'] = $redirectTo;
                }
                
                return 'https://growbal.ai/sso/login?' . http_build_query($params);
            }
        }
        
        // Usage example
        $sso = new GrowbalSSOIntegration();
        
        // When user clicks "Access Growbal" button
        if (isset($_POST['access_growbal'])) {
            // Get current user info (from your session/database)
            $currentUser = getCurrentUser(); // Your function
            
            $redirectUrl = $sso->createGrowbalRedirectUrl(
                $currentUser['id'],
                $currentUser['username'],
                $currentUser['email'],
                '/dashboard' // Optional redirect after login
            );
            
            header('Location: ' . $redirectUrl);
            exit;
        }
        ?>
        '''
        
        return php_code
    
    @staticmethod
    def curl_test_example():
        """cURL examples for testing SSO integration"""
        
        examples = {
            "verify_token": """
            # Test token verification
            curl -X GET "https://growbal.ai/sso/verify-token?token=<JWT_TOKEN>&partner=partner1"
            """,
            
            "sso_login": """
            # Test SSO login
            curl -X GET "https://growbal.ai/sso/login?token=<JWT_TOKEN>&partner=partner1" -v
            """,
            
            "list_partners": """
            # List configured partners
            curl -X GET "https://growbal.ai/sso/partners"
            """,
            
            "authorization_header": """
            # SSO login with Authorization header
            curl -X GET "https://growbal.ai/sso/login?partner=partner1" \\
                 -H "Authorization: Bearer <JWT_TOKEN>" -v
            """
        }
        
        return examples

# Global integration examples instance
partner_integration = PartnerIntegrationExamples()
```

## 6. Security Enhancements

### Create SSO Security Monitor

Create `authentication/sso_security.py`:

```python
"""
Security monitoring and enhancements for SSO
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from .security_utils import security_utils

logger = logging.getLogger(__name__)

class SSOSecurityMonitor:
    """Security monitoring for SSO operations"""
    
    def __init__(self):
        # Track SSO attempts
        self.sso_attempts = defaultdict(list)  # partner_id -> list of attempts
        self.failed_tokens = deque(maxlen=1000)  # Recent failed tokens
        self.partner_stats = defaultdict(lambda: {
            "total_attempts": 0,
            "successful_logins": 0,
            "failed_attempts": 0,
            "unique_users": set(),
            "last_success": None,
            "last_failure": None
        })
        
        # Security alerts
        self.security_alerts = deque(maxlen=100)
        
        # Suspicious patterns
        self.suspicious_patterns = {
            "multiple_partners": {},  # user -> list of partners
            "rapid_attempts": {},     # ip -> list of timestamps
            "token_reuse": {},        # token_hash -> count
        }
    
    def record_sso_attempt(
        self,
        success: bool,
        partner_id: str,
        user_info: Optional[Dict[str, Any]] = None,
        client_ip: str = None,
        error_message: str = None,
        token_payload: Optional[Dict[str, Any]] = None
    ):
        """Record SSO attempt for security analysis"""
        
        attempt = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "partner_id": partner_id,
            "client_ip": client_ip,
            "error_message": error_message,
            "user_id": user_info.get("user_id") if user_info else None,
            "username": user_info.get("username") if user_info else None
        }
        
        # Record attempt
        self.sso_attempts[partner_id].append(attempt)
        
        # Update partner statistics
        stats = self.partner_stats[partner_id]
        stats["total_attempts"] += 1
        
        if success:
            stats["successful_logins"] += 1
            stats["last_success"] = attempt["timestamp"]
            if user_info and user_info.get("user_id"):
                stats["unique_users"].add(user_info["user_id"])
        else:
            stats["failed_attempts"] += 1
            stats["last_failure"] = attempt["timestamp"]
            
            # Record failed token for analysis
            if token_payload:
                self.failed_tokens.append({
                    "timestamp": attempt["timestamp"],
                    "partner_id": partner_id,
                    "payload": token_payload,
                    "error": error_message
                })
        
        # Check for suspicious patterns
        self._check_suspicious_patterns(attempt, token_payload)
        
        # Clean old attempts (keep last 24 hours)
        self._cleanup_old_attempts()
    
    def _check_suspicious_patterns(
        self,
        attempt: Dict[str, Any],
        token_payload: Optional[Dict[str, Any]]
    ):
        """Check for suspicious SSO patterns"""
        
        alerts = []
        
        # Pattern 1: Multiple partners for same user
        if attempt["success"] and attempt["user_id"]:
            user_partners = self.suspicious_patterns["multiple_partners"]
            user_id = attempt["user_id"]
            
            if user_id not in user_partners:
                user_partners[user_id] = []
            
            if attempt["partner_id"] not in user_partners[user_id]:
                user_partners[user_id].append(attempt["partner_id"])
                
                if len(user_partners[user_id]) > 2:  # User from 3+ partners
                    alerts.append({
                        "type": "multiple_partners",
                        "severity": "medium",
                        "message": f"User {user_id} authenticated from {len(user_partners[user_id])} different partners",
                        "details": {"user_id": user_id, "partners": user_partners[user_id]}
                    })
        
        # Pattern 2: Rapid attempts from same IP
        if attempt["client_ip"]:
            rapid_attempts = self.suspicious_patterns["rapid_attempts"]
            client_ip = attempt["client_ip"]
            now = datetime.now()
            
            if client_ip not in rapid_attempts:
                rapid_attempts[client_ip] = []
            
            rapid_attempts[client_ip].append(now)
            
            # Check last 5 minutes
            recent = [t for t in rapid_attempts[client_ip] if (now - t).seconds < 300]
            rapid_attempts[client_ip] = recent
            
            if len(recent) > 10:  # More than 10 attempts in 5 minutes
                alerts.append({
                    "type": "rapid_attempts",
                    "severity": "high",
                    "message": f"Rapid SSO attempts from IP {client_ip}: {len(recent)} in 5 minutes",
                    "details": {"client_ip": client_ip, "attempt_count": len(recent)}
                })
        
        # Pattern 3: Token reuse (if token payload available)
        if token_payload:
            # Create simple hash of critical token parts
            token_signature = f"{token_payload.get('sub')}:{token_payload.get('iat')}:{token_payload.get('exp')}"
            token_hash = hash(token_signature)
            
            token_reuse = self.suspicious_patterns["token_reuse"]
            token_reuse[token_hash] = token_reuse.get(token_hash, 0) + 1
            
            if token_reuse[token_hash] > 3:  # Same token used more than 3 times
                alerts.append({
                    "type": "token_reuse",
                    "severity": "high",
                    "message": f"Potential token reuse detected: {token_reuse[token_hash]} uses",
                    "details": {"token_hash": str(token_hash), "use_count": token_reuse[token_hash]}
                })
        
        # Record alerts
        for alert in alerts:
            self._create_security_alert(alert)
    
    def _create_security_alert(self, alert: Dict[str, Any]):
        """Create and log security alert"""
        
        alert["timestamp"] = datetime.now().isoformat()
        alert["alert_id"] = len(self.security_alerts) + 1
        
        self.security_alerts.append(alert)
        
        # Log alert
        logger.warning(f"SSO_SECURITY_ALERT: {json.dumps(alert)}")
        
        # Could integrate with external alerting systems here
        # await send_slack_alert(alert)
        # await send_email_alert(alert)
    
    def _cleanup_old_attempts(self):
        """Clean up old attempt records"""
        
        cutoff = datetime.now() - timedelta(hours=24)
        
        for partner_id in list(self.sso_attempts.keys()):
            attempts = self.sso_attempts[partner_id]
            recent_attempts = [
                a for a in attempts 
                if datetime.fromisoformat(a["timestamp"]) > cutoff
            ]
            self.sso_attempts[partner_id] = recent_attempts
            
            if not recent_attempts:
                del self.sso_attempts[partner_id]
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get comprehensive security summary"""
        
        # Calculate overall statistics
        total_attempts = sum(stats["total_attempts"] for stats in self.partner_stats.values())
        total_successes = sum(stats["successful_logins"] for stats in self.partner_stats.values())
        total_failures = sum(stats["failed_attempts"] for stats in self.partner_stats.values())
        
        # Partner performance
        partner_summary = {}
        for partner_id, stats in self.partner_stats.items():
            partner_summary[partner_id] = {
                "total_attempts": stats["total_attempts"],
                "success_rate": stats["successful_logins"] / max(stats["total_attempts"], 1),
                "unique_users": len(stats["unique_users"]),
                "last_success": stats["last_success"],
                "last_failure": stats["last_failure"]
            }
        
        # Recent alerts
        recent_alerts = [
            alert for alert in self.security_alerts
            if datetime.fromisoformat(alert["timestamp"]) > datetime.now() - timedelta(hours=1)
        ]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_stats": {
                "total_attempts": total_attempts,
                "total_successes": total_successes,
                "total_failures": total_failures,
                "success_rate": total_successes / max(total_attempts, 1),
                "active_partners": len(self.partner_stats)
            },
            "partner_summary": partner_summary,
            "recent_alerts": recent_alerts,
            "suspicious_patterns": {
                "users_with_multiple_partners": len(self.suspicious_patterns["multiple_partners"]),
                "ips_with_rapid_attempts": len(self.suspicious_patterns["rapid_attempts"]),
                "potential_token_reuse": len([k for k, v in self.suspicious_patterns["token_reuse"].items() if v > 1])
            },
            "failed_token_analysis": self._analyze_failed_tokens()
        }
    
    def _analyze_failed_tokens(self) -> Dict[str, Any]:
        """Analyze patterns in failed tokens"""
        
        if not self.failed_tokens:
            return {"total_failed": 0}
        
        # Group by error type
        error_types = defaultdict(int)
        partner_failures = defaultdict(int)
        
        for failed_token in self.failed_tokens:
            error_types[failed_token["error"]] += 1
            partner_failures[failed_token["partner_id"]] += 1
        
        return {
            "total_failed": len(self.failed_tokens),
            "error_types": dict(error_types),
            "partner_failures": dict(partner_failures),
            "most_common_error": max(error_types, key=error_types.get) if error_types else None
        }

# Global SSO security monitor
sso_security_monitor = SSOSecurityMonitor()
```

## 7. Testing SSO Integration

### Create SSO Tests

Create `authentication/test_sso.py`:

```python
"""
Test SSO integration functionality
"""
import asyncio
import jwt
from datetime import datetime, timezone, timedelta
from .jwt_service import jwt_sso_service
from .jwt_config import JWTConfig

async def test_sso_integration():
    """Test complete SSO integration"""
    print("🧪 Testing JWT SSO integration...")
    
    # Test 1: JWT Configuration validation
    print("\n1. Testing JWT configuration...")
    try:
        valid_partners = JWTConfig.get_all_valid_partners()
        print(f"✅ Found {len(valid_partners)} valid partner configurations")
        
        for partner_id, config in valid_partners.items():
            print(f"   Partner {partner_id}: {config['name']} ({config['algorithm']})")
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    # Test 2: Token generation and verification (for testing)
    print("\n2. Testing token generation and verification...")
    try:
        # Generate test token
        test_user_data = {
            "user_id": "test123",
            "username": "testuser",
            "email": "test@partner.com",
            "full_name": "Test User"
        }
        
        # Only test with partners that have secrets (HS256/HS512)
        test_partner = None
        for partner_id, config in valid_partners.items():
            if config["algorithm"].startswith("HS") and config.get("secret"):
                test_partner = partner_id
                break
        
        if test_partner:
            test_token = jwt_sso_service.generate_test_token(test_partner, test_user_data)
            
            if test_token:
                print(f"✅ Generated test token for partner {test_partner}")
                
                # Verify the token
                success, payload, error = jwt_sso_service.verify_sso_token(test_token, test_partner)
                
                if success:
                    print("✅ Token verification successful")
                    user_info = jwt_sso_service.extract_user_info(payload)
                    print(f"   Extracted user: {user_info['username']} ({user_info['user_id']})")
                else:
                    print(f"❌ Token verification failed: {error}")
            else:
                print("❌ Could not generate test token")
        else:
            print("ℹ️ No HS256/HS512 partners configured for testing")
            
    except Exception as e:
        print(f"❌ Token test failed: {e}")
    
    # Test 3: Security validation
    print("\n3. Testing security validation...")
    try:
        # Test expired token
        expired_payload = {
            "sub": "test123",
            "username": "testuser",
            "email": "test@partner.com",
            "iss": "partner1.com",
            "aud": "growbal.ai",
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),  # Expired
            "iat": int((datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp())
        }
        
        if test_partner and valid_partners[test_partner].get("secret"):
            expired_token = jwt.encode(
                expired_payload,
                valid_partners[test_partner]["secret"],
                algorithm=valid_partners[test_partner]["algorithm"]
            )
            
            success, payload, error = jwt_sso_service.verify_sso_token(expired_token, test_partner)
            
            if not success and "expired" in error.lower():
                print("✅ Expired token correctly rejected")
            else:
                print(f"❌ Expired token handling failed: {error}")
        
    except Exception as e:
        print(f"❌ Security test failed: {e}")
    
    # Test 4: Partner integration examples
    print("\n4. Testing partner integration examples...")
    try:
        from .partner_integration_examples import partner_integration
        
        redirect_examples = partner_integration.generate_redirect_url_example()
        print("✅ Generated partner integration examples")
        print(f"   Example redirect: {redirect_examples['query_parameter']}")
        
    except Exception as e:
        print(f"❌ Integration examples failed: {e}")
    
    print("\n✅ SSO integration testing completed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_sso_integration())
    exit(0 if success else 1)
```

## 8. Production Configuration

### Production Security Configuration

Add to your production configuration:

```python
# Production SSO Configuration
SSO_PRODUCTION_CONFIG = {
    # Security requirements
    "require_https": True,
    "validate_partner_certificates": True,
    "enable_token_replay_protection": True,
    "max_token_age_seconds": 300,  # 5 minutes
    
    # Rate limiting
    "max_sso_attempts_per_ip": 10,
    "sso_rate_limit_window_minutes": 5,
    "max_failed_attempts_per_partner": 100,
    
    # Monitoring
    "log_all_sso_attempts": True,
    "enable_security_monitoring": True,
    "alert_on_suspicious_patterns": True,
    "performance_monitoring": True,
    
    # Partner validation
    "validate_partner_certificates": True,
    "require_partner_ip_whitelist": False,  # Set to True if needed
    "partner_timeout_seconds": 30
}
```

### SSL/TLS Configuration for RSA Partners

```bash
# Generate RSA key pair for testing (partners would provide public key)
openssl genrsa -out partner_private_key.pem 2048
openssl rsa -in partner_private_key.pem -pubout -out partner_public_key.pem

# Verify key format
openssl rsa -in partner_public_key.pem -pubin -text -noout
```

## 9. Testing and Validation

### Pre-Production Checklist

- [ ] JWT configuration validated for all partners
- [ ] Token verification works with all algorithms
- [ ] SSO endpoints respond correctly
- [ ] Security monitoring is active
- [ ] Rate limiting is configured
- [ ] Error handling is comprehensive
- [ ] Integration examples are documented
- [ ] Production security settings applied

### Integration Testing Steps

1. **Test JWT Configuration**:
   ```bash
   python authentication/test_sso.py
   ```

2. **Test SSO Endpoints**:
   ```bash
   # List partners
   curl http://localhost:8000/sso/partners
   
   # Test token verification
   curl "http://localhost:8000/sso/verify-token?token=<TEST_TOKEN>&partner=partner1"
   ```

3. **Test Partner Integration**:
   - Generate test tokens from partner examples
   - Test redirect URLs
   - Verify session creation

### Security Testing

```bash
# Test with expired token
curl "http://localhost:8000/sso/login?token=<EXPIRED_TOKEN>&partner=partner1"

# Test with invalid signature
curl "http://localhost:8000/sso/login?token=<TAMPERED_TOKEN>&partner=partner1"

# Test rate limiting
for i in {1..15}; do curl "http://localhost:8000/sso/login?token=invalid"; done
```

## Next Steps

After completing this phase:

1. Coordinate with partner sites for integration testing
2. Document SSO endpoints and requirements
3. Set up monitoring for SSO usage
4. Proceed to Phase 7: Session Policies Implementation
5. Plan production deployment with partners

## Security Reminders

1. **Token Security**: JWT tokens should be short-lived (5-10 minutes max)
2. **HTTPS Required**: All SSO communication must use HTTPS
3. **Key Management**: Securely manage shared secrets and public keys
4. **Rate Limiting**: Implement proper rate limiting for SSO endpoints
5. **Monitoring**: Monitor all SSO attempts for security anomalies
6. **Partner Validation**: Validate partner authenticity and trustworthiness
7. **Error Handling**: Don't expose sensitive information in error messages
8. **Audit Logging**: Log all SSO events for security auditing