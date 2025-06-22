#!/usr/bin/env python3
"""
Test email sending functionality
"""

import sys
import subprocess

def test_email_sending():
    """Test email sending from Apache container"""
    print("Testing email sending from Apache container...")
    
    # Test using the authentication system's email sender
    test_script = '''
import sys
sys.path.append("/var/www/cgi-bin/lib")
from email_sender import EmailSender

sender = EmailSender()
try:
    success = sender.send_confirmation_email(
        to_email="test@test.local",
        username="testuser",
        confirmation_url="https://example.com/confirm?token=testtoken"
    )
    print(f"Email send result: {success}")
    if success:
        print("✓ Email sent successfully")
    else:
        print("✗ Email failed to send")
except Exception as e:
    print(f"✗ Email error: {e}")
'''
    
    try:
        # Run the test script inside the Apache container
        cmd = f"podman exec podplay-apache python3 -c '{test_script}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0 and "Email sent successfully" in result.stdout
        
    except subprocess.TimeoutExpired:
        print("✗ Email test timed out")
        return False
    except Exception as e:
        print(f"✗ Email test error: {e}")
        return False

def test_smtp_connectivity():
    """Test basic SMTP connectivity"""
    print("Testing SMTP connectivity...")
    
    # Simple SMTP test using telnet
    test_script = '''
import smtplib
try:
    with smtplib.SMTP("localhost", 25, timeout=10) as server:
        server.noop()  # Simple test
    print("✓ SMTP connection successful")
except Exception as e:
    print(f"✗ SMTP connection failed: {e}")
'''
    
    try:
        cmd = f"podman exec podplay-apache python3 -c '{test_script}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return "SMTP connection successful" in result.stdout
        
    except Exception as e:
        print(f"✗ SMTP test error: {e}")
        return False

def check_mail_logs():
    """Check mail server logs for any issues"""
    print("Checking mail server logs...")
    
    try:
        result = subprocess.run(
            "podman logs --tail 10 podplay-mail", 
            shell=True, 
            capture_output=True, 
            text=True
        )
        
        print("Recent mail server logs:")
        print(result.stdout)
        
        if "error" in result.stdout.lower():
            return False
        return True
        
    except Exception as e:
        print(f"✗ Failed to check logs: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Email Testing Suite")
    print("=" * 50)
    
    tests = [
        ("SMTP Connectivity", test_smtp_connectivity),
        ("Email Sending", test_email_sending),
        ("Mail Logs Check", check_mail_logs)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        print()
    
    total = len(tests)
    print("=" * 50)
    print(f"Email tests: {passed}/{total} passed")
    
    sys.exit(0 if passed == total else 1)