"""
Integration testing for authentication system
"""
import asyncio
import json
from ..auth_service import auth_service
from ..password_service import password_service
from ..user_repository import user_repository
from ..models import LoginRequest

async def run_integration_tests():
    """Run comprehensive integration tests"""
    print("Running authentication integration tests...")
    
    test_results = []
    
    # Test 1: Database connectivity
    print("\n1. Testing database connectivity...")
    try:
        structure = user_repository.verify_database_structure()
        if structure["connection_status"] == "success":
            test_results.append(("Database Connectivity", "PASS"))
            print(f"   Connected to database with {structure['total_users']} users")
        else:
            test_results.append(("Database Connectivity", "FAIL"))
            print(f"   Database connection failed: {structure.get('error')}")
    except Exception as e:
        test_results.append(("Database Connectivity", f"FAIL - {e}"))
    
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
            test_results.append(("Password Service", "PASS"))
            print("   Password hashing and verification working correctly")
        else:
            test_results.append(("Password Service", "FAIL"))
            print("   Password verification not working correctly")
    except Exception as e:
        test_results.append(("Password Service", f"FAIL - {e}"))
    
    # Test 3: Authentication service (requires test user)
    print("\n3. Testing authentication service...")
    try:
        # Test with invalid credentials
        invalid_login = LoginRequest(email="nonexistent@example.com", password="invalid")
        invalid_result = await auth_service.authenticate_user(invalid_login)
        
        if not invalid_result.success:
            test_results.append(("Authentication - Invalid User", "PASS"))
            print("   Invalid user correctly rejected")
        else:
            test_results.append(("Authentication - Invalid User", "FAIL"))
            print("   Invalid user incorrectly accepted")
        
        # Test password strength validation
        strength_test = auth_service.validate_password_strength("WeakPass")
        if not strength_test['is_valid']:
            test_results.append(("Password Strength Validation", "PASS"))
            print("   Weak password correctly rejected")
        else:
            test_results.append(("Password Strength Validation", "FAIL"))
            print("   Weak password incorrectly accepted")
            
    except Exception as e:
        test_results.append(("Authentication Service", f"FAIL - {e}"))
    
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
        print("\nAll tests passed! Authentication system is ready.")
    else:
        print(f"\nWARNING: {failed} test(s) failed. Please review and fix issues.")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    exit(0 if success else 1)