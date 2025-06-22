#!/usr/bin/env python3
"""
Minimal authentication test to verify basic functionality
"""

import sys
import time
import subprocess
from auth_client import SimpleAuthClient
import test_config as config


def test_csrf_token():
    """Test CSRF token generation"""
    client = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    if client.get_csrf_token():
        print("✓ CSRF token generation: WORKING")
        return True
    else:
        print("✗ CSRF token generation: FAILED")
        return False


def test_registration_creates_token():
    """Test that registration creates a pending token"""
    client = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    timestamp = int(time.time())
    username = f"minimal{timestamp}"
    email = f"minimal{timestamp}@test.local"
    password = "TestPass123!"
    
    # Try to register
    client.register(username, email, password)
    
    # Check if token was created (regardless of email)
    try:
        cmd = f"podman exec {config.CONTAINER_NAME} ls /data/user-data/pending/registrations/ | grep -c '.yaml'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        
        if count > 0:
            print(f"✓ Registration token creation: WORKING ({count} tokens found)")
            return True
        else:
            print("✗ Registration token creation: FAILED")
            return False
    except:
        print("✗ Registration token creation: ERROR")
        return False


def test_portal_protection():
    """Test that portal requires authentication"""
    client = SimpleAuthClient(config.BASE_URL, config.SSL_VERIFY)
    
    if client.access_portal():
        print("✗ Portal protection: FAILED (accessible without auth)")
        return False
    else:
        print("✓ Portal protection: WORKING (redirects without auth)")
        return True


def run_minimal_tests():
    """Run minimal test suite"""
    print("Running minimal authentication tests...")
    print("=" * 50)
    
    tests = [
        test_csrf_token,
        test_registration_creates_token,
        test_portal_protection
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    total = len(tests)
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    # Quick service check
    try:
        result = subprocess.run(
            f"podman ps --filter name={config.CONTAINER_NAME} --format '{{{{.Names}}}}'",
            shell=True, capture_output=True, text=True
        )
        if config.CONTAINER_NAME not in result.stdout:
            print(f"❌ Container '{config.CONTAINER_NAME}' is not running")
            sys.exit(1)
    except:
        print("❌ Cannot check container status")
        sys.exit(1)
    
    success = run_minimal_tests()
    sys.exit(0 if success else 1)