#!/usr/bin/env python3
"""
Simple authentication testing for PodPlay
Tests core authentication workflows without complexity
"""

import sys
import time
import subprocess
from auth_client import SimpleAuthClient
import test_config as config


def get_email_token(email, token_type):
    """Get token from container filesystem"""
    try:
        # List files in pending directory
        cmd = f"podman exec {config.CONTAINER_NAME} ls /data/user-data/pending/{token_type}s/"
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        
        if result.returncode != 0:
            return None
        
        # Find token file for email
        for filename in result.stdout.split():
            if filename.endswith('.yaml'):
                # Read file content
                cmd = f"podman exec {config.CONTAINER_NAME} cat /data/user-data/pending/{token_type}s/{filename}"
                content = subprocess.run(cmd.split(), capture_output=True, text=True).stdout
                
                # Check if it's for our email
                if email in content:
                    return filename.replace('.yaml', '')
        
        return None
    except:
        return None


def wait_for_token(email, token_type, max_wait=10):
    """Wait for email token to appear"""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        token = get_email_token(email, token_type)
        if token:
            return token
        time.sleep(1)
    
    return None


def test_registration_flow():
    """Test user registration and confirmation"""
    client = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    # Generate unique test user
    timestamp = int(time.time())
    username = f"testuser{timestamp}"
    email = f"test{timestamp}@{config.DEFAULT_DOMAIN}"
    password = "TestPass123!"
    
    # Register user
    success = client.register(username, email, password)
    if not success:
        # Check if registration created a pending token (email might fail)
        token = wait_for_token(email, "registration", max_wait=2)
        if not token:
            return False, "Registration failed - no pending registration created"
        # If we have a token, the registration worked but email failed
        print(f"  Note: Registration created but email failed (using token directly)")
    
    # Wait for confirmation token
    token = wait_for_token(email, "registration")
    if not token:
        return False, "No confirmation token found"
    
    # Confirm registration
    success = client.confirm_registration(token)
    if not success:
        return False, "Confirmation failed"
    
    # Test login - use full email address
    success = client.login(email, password, domain=config.DEFAULT_DOMAIN)
    if not success:
        return False, "Login failed after confirmation"
    
    return True, "Registration flow completed"


def test_password_reset_flow():
    """Test password reset workflow"""
    client = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    # First create and confirm a user
    timestamp = int(time.time())
    username = f"resetuser{timestamp}"
    email = f"reset{timestamp}@{config.DEFAULT_DOMAIN}"
    password = "OldPass123!"
    new_password = "NewPass456!"
    
    # Register and confirm user
    success = client.register(username, email, password)
    if not success:
        # Check if registration created a pending token
        token = wait_for_token(email, "registration", max_wait=2)
        if not token:
            return False, "Failed to register user for reset test"
        print(f"  Note: Registration created but email failed (using token directly)")
    
    token = wait_for_token(email, "registration")
    if not token or not client.confirm_registration(token):
        return False, "Failed to confirm user for reset test"
    
    # Request password reset
    success = client.request_password_reset(email)
    if not success:
        return False, "Password reset request failed"
    
    # Wait for reset token
    reset_token = wait_for_token(email, "reset")
    if not reset_token:
        return False, "No reset token found"
    
    # Complete password reset
    success = client.reset_password(reset_token, new_password)
    if not success:
        return False, "Password reset failed"
    
    # Test login with new password
    success = client.login(email, new_password, domain=config.DEFAULT_DOMAIN)
    if not success:
        return False, "Login failed with new password"
    
    # Verify old password doesn't work
    client2 = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    if client2.login(email, password, domain=config.DEFAULT_DOMAIN):
        return False, "Old password still works"
    
    return True, "Password reset flow completed"


def test_portal_protection():
    """Test portal access control"""
    # Test without authentication
    client1 = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    if client1.access_portal():
        return False, "Portal accessible without authentication"
    
    # Create and login user
    timestamp = int(time.time())
    username = f"portaluser{timestamp}"
    email = f"portal{timestamp}@{config.DEFAULT_DOMAIN}"
    password = "PortalPass123!"
    
    client2 = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    # Register and confirm
    success = client2.register(username, email, password)
    if not success:
        # Check if registration created a pending token
        token = wait_for_token(email, "registration", max_wait=2)
        if not token:
            return False, "Failed to register portal test user"
        print(f"  Note: Registration created but email failed (using token directly)")
    
    token = wait_for_token(email, "registration")
    if not token or not client2.confirm_registration(token):
        return False, "Failed to confirm portal test user"
    
    # Login
    if not client2.login(email, password, domain=config.DEFAULT_DOMAIN):
        return False, "Failed to login portal test user"
    
    # Now portal should be accessible
    if not client2.access_portal():
        return False, "Portal not accessible after login"
    
    # Logout and verify portal is protected again
    client2.logout()
    if client2.access_portal():
        return False, "Portal still accessible after logout"
    
    return True, "Portal protection working correctly"


def run_tests():
    """Run all tests and report results"""
    tests = [
        ("Registration flow", test_registration_flow),
        ("Password reset flow", test_password_reset_flow),
        ("Portal protection", test_portal_protection)
    ]
    
    print("Running authentication tests...")
    print("=" * 50)
    
    passed = 0
    failed = 0
    start_time = time.time()
    
    for test_name, test_func in tests:
        print(f"\nTesting: {test_name}")
        try:
            success, message = test_func()
            if success:
                print(f"✓ {test_name}: PASSED")
                passed += 1
            else:
                print(f"✗ {test_name}: FAILED - {message}")
                failed += 1
        except Exception as e:
            print(f"✗ {test_name}: ERROR - {str(e)}")
            failed += 1
    
    duration = time.time() - start_time
    
    print("\n" + "=" * 50)
    print(f"Tests: {passed} passed, {failed} failed")
    print(f"Duration: {duration:.1f} seconds")
    
    if failed == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {failed} test(s) failed")
    
    return failed == 0


def check_services():
    """Quick check that services are running"""
    try:
        # Check if container is running
        cmd = f"podman ps --filter name={config.CONTAINER_NAME} --format '{{{{.Names}}}}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if config.CONTAINER_NAME not in result.stdout:
            print(f"❌ Container '{config.CONTAINER_NAME}' is not running")
            print("Please start the services with: make pod-up")
            return False
        
        # Quick HTTP check
        import requests
        import urllib3
        urllib3.disable_warnings()
        
        try:
            response = requests.get(f"{config.BASE_URL}/", verify=False, timeout=5)
            if response.status_code != 200:
                print(f"❌ Service not responding correctly (HTTP {response.status_code})")
                return False
        except:
            print(f"❌ Cannot connect to {config.BASE_URL}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Service check failed: {e}")
        return False


if __name__ == "__main__":
    # Check services first
    if not check_services():
        sys.exit(1)
    
    # Run tests
    success = run_tests()
    sys.exit(0 if success else 1)