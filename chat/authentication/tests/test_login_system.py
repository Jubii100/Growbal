"""
Test the login system integration
"""
import asyncio
from ..models import LoginRequest
from ..auth_service import auth_service

async def test_login_flow():
    """Test the complete login flow"""
    print("Testing login system integration...")
    
    # Test 1: Test authentication service directly
    print("\n1. Testing authentication service...")
    
    # Test invalid credentials
    invalid_login = LoginRequest(email="invalid@example.com", password="invalid")
    invalid_result = await auth_service.authenticate_user(invalid_login)
    print(f"Invalid credentials rejected: {not invalid_result.success}")
    
    # Test 2: Test password strength validation
    print("\n2. Testing password strength validation...")
    passwords = ["weak", "StrongPass123!", "VeryWeakPassword", "ComplexP@ssw0rd2024!"]
    
    for pwd in passwords:
        strength = auth_service.validate_password_strength(pwd)
        print(f"Password '{pwd}': Score {strength['strength_score']}/100, Valid: {strength['is_valid']}")
    
    # Test 3: Test form submission (would need test user)
    print("\n3. Testing form submission...")
    print("Note: Requires test user in database for full integration test")
    print("To test manually:")
    print("  1. Start the application: python main.py")
    print("  2. Visit: http://localhost:8000/login")
    print("  3. Try logging in with test credentials")
    
    print("\nLogin system basic tests completed!")

if __name__ == "__main__":
    asyncio.run(test_login_flow())