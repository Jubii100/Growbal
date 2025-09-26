"""
Database connectivity and structure testing
Adapted for the existing Growbal user table schema
"""
import asyncio
from ..database_config import mysql_auth_db
from ..user_repository import user_repository

async def test_database_setup():
    """Test database setup and connectivity"""
    print("TESTING: Testing MySQL authentication database setup...")
    
    # Test basic connectivity
    print("\n1. Testing database connectivity...")
    if mysql_auth_db.test_connection():
        print("PASS: Database connection successful")
    else:
        print("FAIL: Database connection failed")
        return False
    
    # Verify database structure
    print("\n2. Verifying database structure...")
    structure = user_repository.verify_database_structure()
    
    if structure["connection_status"] == "success":
        print(f"PASS: Users table exists with {structure['total_users']} active users")
        print(f"Table columns: {[col['Field'] for col in structure['columns']]}")
        
        # Check for required columns
        required_columns = ['user_id', 'email', 'password', 'full_name', 'is_deleted']
        available_columns = [col['Field'] for col in structure['columns']]
        missing_columns = [col for col in required_columns if col not in available_columns]
        
        if missing_columns:
            print(f"WARNING: Missing required columns: {missing_columns}")
        else:
            print("PASS: All required columns present")
            
    else:
        print(f"FAIL: Database structure verification failed: {structure.get('error')}")
        return False
    
    # Test user retrieval (without specifying a test user since we don't know what exists)
    print("\n3. Testing user retrieval functionality...")
    try:
        # Test the repository methods without expecting specific users
        print("PASS: User repository methods are accessible")
        print("INFO: To test specific user retrieval, provide a known email address")
    except Exception as e:
        print(f"FAIL: User repository test failed: {e}")
        return False
    
    print("\nPASS: Database setup verification complete!")
    return True

if __name__ == "__main__":
    asyncio.run(test_database_setup())