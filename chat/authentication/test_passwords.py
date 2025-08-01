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
        email="test@example.com",  # Replace with actual email
        password="testpassword123"  # Replace with actual password
    )
    
    auth_result = await auth_service.authenticate_user(test_login)
    
    if auth_result.success:
        print(f"✅ Authentication successful: {auth_result.user.email}")
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