# Phase 1: Database Setup and MySQL Integration

## Overview

This phase establishes connectivity to the external MySQL database containing user credentials and sets up the necessary data models for authentication.

## Prerequisites

- MySQL database with user credentials table
- BCrypt-hashed passwords in format `$2a$10$...`
- Database connection credentials

## 1. Database Connection Configuration

### Install Required Dependencies

```bash
pip install pymysql sqlalchemy
```

### Create Database Connection Module

Create `authentication/database_config.py`:

```python
"""
MySQL Database Configuration for User Authentication
"""
import os
import pymysql
from typing import Optional, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MySQLUserDatabase:
    """MySQL database connection for user authentication"""
    
    def __init__(self):
        self.host = os.getenv('MYSQL_AUTH_HOST', 'localhost')
        self.port = int(os.getenv('MYSQL_AUTH_PORT', 3306))
        self.username = os.getenv('MYSQL_AUTH_USERNAME')
        self.password = os.getenv('MYSQL_AUTH_PASSWORD')
        self.database = os.getenv('MYSQL_AUTH_DATABASE')
        
        if not all([self.username, self.password, self.database]):
            raise ValueError("MySQL authentication database credentials not configured")
        
        # Create SQLAlchemy engine
        self.connection_string = f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        self.engine = create_engine(
            self.connection_string,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup"""
        connection = None
        try:
            connection = self.engine.connect()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            raise e
        finally:
            if connection:
                connection.close()
    
    @contextmanager
    def get_session(self):
        """Get SQLAlchemy session with automatic cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            print(f"Database connection test failed: {e}")
            return False

# Global instance
mysql_auth_db = MySQLUserDatabase()
```

### Environment Configuration

Add to your `.env` file:

```bash
# MySQL Authentication Database
MYSQL_AUTH_HOST=your-mysql-host
MYSQL_AUTH_PORT=3306
MYSQL_AUTH_USERNAME=your-mysql-username
MYSQL_AUTH_PASSWORD=your-mysql-password
MYSQL_AUTH_DATABASE=your-mysql-database
```

## 2. User Model Definition

### Create Authentication Models

Create `authentication/models.py`:

```python
"""
Authentication models and user data structures
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class AuthUser:
    """Represents a user from the authentication database"""
    user_id: int
    username: str
    email: Optional[str]
    password_hash: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthUser':
        """Create from dictionary (for session retrieval)"""
        return cls(
            user_id=data['user_id'],
            username=data['username'],
            email=data.get('email'),
            password_hash='',  # Never store password hash in session
            is_active=data.get('is_active', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            last_login=datetime.fromisoformat(data['last_login']) if data.get('last_login') else None,
            metadata=data.get('metadata', {})
        )

@dataclass
class LoginRequest:
    """Login request data structure"""
    username: str
    password: str
    remember_me: bool = False

@dataclass
class AuthenticationResult:
    """Authentication result with user data and session info"""
    success: bool
    user: Optional[AuthUser] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None
```

## 3. User Repository Implementation

### Create User Data Access Layer

Create `authentication/user_repository.py`:

```python
"""
User repository for authentication database operations
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from .database_config import mysql_auth_db
from .models import AuthUser
import logging

logger = logging.getLogger(__name__)

class UserRepository:
    """Repository for user authentication operations"""
    
    def __init__(self):
        self.db = mysql_auth_db
    
    def get_user_by_username(self, username: str) -> Optional[AuthUser]:
        """
        Retrieve user by username from MySQL database
        
        Args:
            username: Username to search for
            
        Returns:
            AuthUser object or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                # Adjust query based on your actual table structure
                query = text("""
                    SELECT user_id, username, email, password_hash, 
                           is_active, created_at, last_login, metadata
                    FROM users 
                    WHERE username = :username AND is_active = 1
                    LIMIT 1
                """)
                
                result = conn.execute(query, {"username": username})
                row = result.fetchone()
                
                if row:
                    return AuthUser(
                        user_id=row.user_id,
                        username=row.username,
                        email=row.email,
                        password_hash=row.password_hash,
                        is_active=bool(row.is_active),
                        created_at=row.created_at,
                        last_login=row.last_login,
                        metadata=row.metadata if hasattr(row, 'metadata') else {}
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user {username}: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[AuthUser]:
        """
        Retrieve user by email from MySQL database
        
        Args:
            email: Email address to search for
            
        Returns:
            AuthUser object or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                query = text("""
                    SELECT user_id, username, email, password_hash, 
                           is_active, created_at, last_login, metadata
                    FROM users 
                    WHERE email = :email AND is_active = 1
                    LIMIT 1
                """)
                
                result = conn.execute(query, {"email": email})
                row = result.fetchone()
                
                if row:
                    return AuthUser(
                        user_id=row.user_id,
                        username=row.username,
                        email=row.email,
                        password_hash=row.password_hash,
                        is_active=bool(row.is_active),
                        created_at=row.created_at,
                        last_login=row.last_login,
                        metadata=row.metadata if hasattr(row, 'metadata') else {}
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user by email {email}: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[AuthUser]:
        """
        Retrieve user by ID from MySQL database
        
        Args:
            user_id: User ID to search for
            
        Returns:
            AuthUser object or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                query = text("""
                    SELECT user_id, username, email, password_hash, 
                           is_active, created_at, last_login, metadata
                    FROM users 
                    WHERE user_id = :user_id AND is_active = 1
                    LIMIT 1
                """)
                
                result = conn.execute(query, {"user_id": user_id})
                row = result.fetchone()
                
                if row:
                    return AuthUser(
                        user_id=row.user_id,
                        username=row.username,
                        email=row.email,
                        password_hash=row.password_hash,
                        is_active=bool(row.is_active),
                        created_at=row.created_at,
                        last_login=row.last_login,
                        metadata=row.metadata if hasattr(row, 'metadata') else {}
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user by ID {user_id}: {e}")
            return None
    
    def update_last_login(self, user_id: int) -> bool:
        """
        Update user's last login timestamp
        
        Args:
            user_id: User ID to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                query = text("""
                    UPDATE users 
                    SET last_login = NOW() 
                    WHERE user_id = :user_id
                """)
                
                result = conn.execute(query, {"user_id": user_id})
                conn.commit()
                
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            return False
    
    def verify_database_structure(self) -> Dict[str, Any]:
        """
        Verify the database structure and return table information
        
        Returns:
            Dictionary with table structure information
        """
        try:
            with self.db.get_connection() as conn:
                # Get table structure
                query = text("DESCRIBE users")
                result = conn.execute(query)
                columns = [dict(row._mapping) for row in result.fetchall()]
                
                # Get row count
                count_query = text("SELECT COUNT(*) as total FROM users")
                count_result = conn.execute(count_query)
                total_users = count_result.fetchone().total
                
                return {
                    "table_exists": True,
                    "columns": columns,
                    "total_users": total_users,
                    "connection_status": "success"
                }
                
        except Exception as e:
            logger.error(f"Error verifying database structure: {e}")
            return {
                "table_exists": False,
                "error": str(e),
                "connection_status": "failed"
            }

# Global repository instance
user_repository = UserRepository()
```

## 4. Integration with Existing Session Management

### Extend ChatSession Model

Add authentication-related fields to your existing ChatSession model in `growbal_django/chats/models.py`:

```python
# Add these imports at the top
from django.contrib.auth import get_user_model

# Add these fields to the ChatSession model (after line 31)
auth_user_id = models.IntegerField(
    null=True,
    blank=True,
    help_text="External MySQL user ID for authenticated users"
)
is_authenticated = models.BooleanField(
    default=False,
    help_text="Whether this session is authenticated"
)
authentication_method = models.CharField(
    max_length=20,
    choices=[
        ('form', 'Form Login'),
        ('sso', 'Single Sign-On'),
        ('anonymous', 'Anonymous')
    ],
    default='anonymous',
    help_text="Method used for authentication"
)
```

### Database Migration

Create and run a Django migration:

```bash
cd growbal_django
python manage.py makemigrations chats
python manage.py migrate
```

## 5. Database Testing and Validation

### Create Database Test Script

Create `authentication/test_database.py`:

```python
"""
Database connectivity and structure testing
"""
import asyncio
from .database_config import mysql_auth_db
from .user_repository import user_repository

async def test_database_setup():
    """Test database setup and connectivity"""
    print("🔍 Testing MySQL authentication database setup...")
    
    # Test basic connectivity
    print("\n1. Testing database connectivity...")
    if mysql_auth_db.test_connection():
        print("✅ Database connection successful")
    else:
        print("❌ Database connection failed")
        return False
    
    # Verify database structure
    print("\n2. Verifying database structure...")
    structure = user_repository.verify_database_structure()
    
    if structure["connection_status"] == "success":
        print(f"✅ Users table exists with {structure['total_users']} users")
        print(f"📊 Table columns: {[col['Field'] for col in structure['columns']]}")
    else:
        print(f"❌ Database structure verification failed: {structure.get('error')}")
        return False
    
    # Test user retrieval (if test user exists)
    print("\n3. Testing user retrieval...")
    # Replace 'testuser' with an actual username from your database
    test_user = user_repository.get_user_by_username('testuser')
    if test_user:
        print(f"✅ Test user retrieved: {test_user.username} (ID: {test_user.user_id})")
    else:
        print("ℹ️ No test user found (this is normal if no test user exists)")
    
    print("\n✅ Database setup verification complete!")
    return True

if __name__ == "__main__":
    asyncio.run(test_database_setup())
```

## 6. Configuration Checklist

### Pre-Implementation Checklist

- [ ] MySQL database credentials configured in `.env`
- [ ] Database connection tested successfully
- [ ] User table structure verified
- [ ] SQLAlchemy dependencies installed
- [ ] Django migration for ChatSession completed
- [ ] Test script runs without errors

### Security Considerations

1. **Connection Security**:
   - Use SSL connections for production MySQL
   - Implement connection pooling limits
   - Use environment variables for credentials

2. **Database Access**:
   - Create dedicated MySQL user with minimal privileges
   - Use parameterized queries to prevent SQL injection
   - Implement proper error handling and logging

3. **Data Privacy**:
   - Never log password hashes
   - Implement secure session storage
   - Use HTTPOnly and Secure cookie attributes

## Next Steps

After completing this phase:

1. Verify all database connections are working
2. Run the test script to validate setup
3. Proceed to Phase 2: Password Verification Implementation
4. Document any database-specific customizations needed

## Troubleshooting

### Common Issues

1. **Connection Refused**: Check MySQL host, port, and firewall settings
2. **Authentication Failed**: Verify username/password and user privileges
3. **Table Not Found**: Ensure your users table name matches the queries
4. **Import Errors**: Check that all dependencies are installed

### Configuration Verification

```bash
# Test database connectivity
python -c "from authentication.database_config import mysql_auth_db; print('✅ Success' if mysql_auth_db.test_connection() else '❌ Failed')"

# Run full database test
python authentication/test_database.py
```