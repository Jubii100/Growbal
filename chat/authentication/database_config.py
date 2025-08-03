"""
MySQL Database Configuration for User Authentication
"""
import os
import pymysql
from typing import Optional, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import URL
from dotenv import load_dotenv

# Load environment variables
load_dotenv('1.env')

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
        #self.connection_string = f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        connection_url = URL.create(
            drivername='mysql+pymysql',
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
)
        self.engine = create_engine(
            #self.connection_string,
            connection_url,
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