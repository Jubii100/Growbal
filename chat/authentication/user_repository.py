"""
User repository for authentication database operations
Adapted for the existing Growbal user table schema
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
                    SELECT user_id, email, full_name, password, phone, role, 
                           is_deleted, creation_date, provider, provider_id, confirm_email
                    FROM user 
                    WHERE email = :email AND is_deleted = 0
                    LIMIT 1
                """)
                
                result = conn.execute(query, {"email": email})
                row = result.fetchone()
                
                if row:
                    return AuthUser(
                        user_id=row.user_id,
                        email=row.email,
                        full_name=row.full_name,
                        password_hash=row.password,
                        phone=row.phone,
                        role=row.role,
                        is_active = not bool(row.is_deleted[0]),
                        is_deleted=bool(row.is_deleted[0]),
                        created_at=row.creation_date,
                        provider=row.provider,
                        provider_id=row.provider_id,
                        confirm_email=bool(row.confirm_email),
                        metadata={}
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user by email {email}: {e}")
            return None
    
    def get_user_by_phone(self, phone: str) -> Optional[AuthUser]:
        """
        Retrieve user by phone from MySQL database
        
        Args:
            phone: Phone number to search for
            
        Returns:
            AuthUser object or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                query = text("""
                    SELECT user_id, email, full_name, password, phone, role, 
                           is_deleted, creation_date, provider, provider_id, confirm_email
                    FROM user 
                    WHERE phone = :phone AND is_deleted = 0
                    LIMIT 1
                """)
                
                result = conn.execute(query, {"phone": phone})
                row = result.fetchone()
                
                if row:
                    return AuthUser(
                        user_id=row.user_id,
                        email=row.email,
                        full_name=row.full_name,
                        password_hash=row.password,
                        phone=row.phone,
                        role=row.role,
                        is_active = not bool(row.is_deleted[0]),
                        is_deleted=bool(row.is_deleted[0]),
                        created_at=row.creation_date,
                        provider=row.provider,
                        provider_id=row.provider_id,
                        confirm_email=bool(row.confirm_email),
                        metadata={}
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user by phone {phone}: {e}")
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
                    SELECT user_id, email, full_name, password, phone, role, 
                           is_deleted, creation_date, provider, provider_id, confirm_email
                    FROM user 
                    WHERE user_id = :user_id AND is_deleted = 0
                    LIMIT 1
                """)
                
                result = conn.execute(query, {"user_id": user_id})
                row = result.fetchone()
                
                if row:
                    return AuthUser(
                        user_id=row.user_id,
                        email=row.email,
                        full_name=row.full_name,
                        password_hash=row.password,
                        phone=row.phone,
                        role=row.role,
                        is_active = not bool(row.is_deleted[0]),
                        is_deleted=bool(row.is_deleted[0]),
                        created_at=row.creation_date,
                        provider=row.provider,
                        provider_id=row.provider_id,
                        confirm_email=bool(row.confirm_email),
                        metadata={}
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user by ID {user_id}: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[AuthUser]:
        """
        Retrieve user by username (email) for compatibility
        
        Args:
            username: Username (email) to search for
            
        Returns:
            AuthUser object or None if not found
        """
        # Since there's no username field, treat username as email
        return self.get_user_by_email(username)
    
    def verify_database_structure(self) -> Dict[str, Any]:
        """
        Verify the database structure and return table information
        
        Returns:
            Dictionary with table structure information
        """
        try:
            with self.db.get_connection() as conn:
                # Get table structure
                query = text("DESCRIBE user")
                result = conn.execute(query)
                columns = [dict(row._mapping) for row in result.fetchall()]
                
                # Get row count
                count_query = text("SELECT COUNT(*) as total FROM user WHERE is_deleted = 0")
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