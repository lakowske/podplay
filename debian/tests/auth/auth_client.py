#!/usr/bin/env python3
"""
Simple HTTP client for authentication testing
"""

import requests
import json
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SimpleAuthClient:
    """Basic HTTP client for authentication testing"""
    
    def __init__(self, base_url, verify_ssl=False):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.csrf_token = None
        
        # Configure retry strategy for connection issues
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set timeouts and connection settings
        self.session.timeout = 30
        self.session.headers.update({
            'Connection': 'close'  # Prevent connection reuse issues
        })
    
    def get_csrf_token(self):
        """Get CSRF token from server"""
        try:
            response = self.session.get(
                f"{self.base_url}/cgi-bin/csrf-token.py",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.csrf_token = data.get('csrf_token')
                return True
        except Exception as e:
            print(f"CSRF token error: {e}")
        return False
    
    def register(self, username, email, password):
        """Register a new user"""
        if not self.csrf_token:
            self.get_csrf_token()
        
        data = {
            'username': username,
            'email': email,
            'password': password,
            'confirm_password': password,
            'csrf_token': self.csrf_token
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/cgi-bin/register.py",
                data=data,
                timeout=30,
                headers={'Connection': 'close'}
            )
            
            # Handle different response scenarios
            if response.status_code == 200:
                # Check for success indicators
                success_indicators = [
                    'Registration Successful' in response.text,
                    'Registration successful' in response.text,
                    'check your email' in response.text.lower()
                ]
                success = any(success_indicators)
                
                if not success:
                    # Debug: show what we got
                    if 'error' in response.text.lower():
                        print(f"Registration error in response")
                        # Extract error message if visible
                        if 'class="error"' in response.text:
                            import re
                            error_match = re.search(r'class="error"[^>]*>([^<]+)', response.text)
                            if error_match:
                                print(f"  Error: {error_match.group(1).strip()}")
                return success
            else:
                print(f"Registration failed with status: {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError as e:
            # Handle connection issues more gracefully
            print(f"Connection error during registration: {e}")
            # Try to determine if registration actually succeeded by checking for pending files
            return self._check_registration_created(email)
        except Exception as e:
            print(f"Registration error: {e}")
            return False
    
    def _check_registration_created(self, email):
        """Check if registration was created despite connection error"""
        import subprocess
        try:
            # Check for pending registration files
            cmd = f"podman exec podplay-apache ls /data/user-data/pending/registrations/"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            
            if result.returncode == 0:
                for filename in result.stdout.split():
                    if filename.endswith('.yaml'):
                        # Read file content to check if it's for our email
                        cmd = f"podman exec podplay-apache cat /data/user-data/pending/registrations/{filename}"
                        content = subprocess.run(cmd.split(), capture_output=True, text=True).stdout
                        if email in content:
                            print(f"  Note: Registration created but connection failed (found pending file)")
                            return True
        except:
            pass
        return False
    
    def login(self, username, password, domain="lab.sethlakowske.com"):
        """Login with credentials"""
        if not self.csrf_token:
            self.get_csrf_token()
        
        data = {
            'username': username,
            'password': password,
            'domain': domain,
            'csrf_token': self.csrf_token
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/cgi-bin/auth.py",
                data=data,
                timeout=30,
                headers={'Connection': 'close'}
            )
            # Check for successful login indicators
            success_indicators = [
                'Login successful' in response.text,
                'Redirecting' in response.text,
                'meta http-equiv="refresh"' in response.text,
                'session_id=' in response.headers.get('Set-Cookie', '')
            ]
            return response.status_code == 200 and any(success_indicators)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error during login: {e}")
            return False
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def confirm_registration(self, token):
        """Confirm registration with token"""
        try:
            response = self.session.get(
                f"{self.base_url}/cgi-bin/confirm.py?token={token}",
                timeout=30,
                headers={'Connection': 'close'}
            )
            success_indicators = [
                'account confirmed' in response.text.lower(),
                'confirmed successfully' in response.text.lower(),
                'confirmation successful' in response.text.lower()
            ]
            success = response.status_code == 200 and any(success_indicators)
            
            # Debug: show what we actually got
            if not success:
                print(f"  Confirmation debug - Status: {response.status_code}")
                print(f"  Confirmation debug - Contains 'account confirmed': {'account confirmed' in response.text.lower()}")
                if 'confirmation error' in response.text.lower():
                    # Extract error message
                    import re
                    error_match = re.search(r'class=\"error\"[^>]*>([^<]+)', response.text)
                    if error_match:
                        print(f"  Confirmation error: {error_match.group(1).strip()}")
                print(f"  Confirmation debug - Response snippet: {response.text[:400]}...")
            
            return success
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error during confirmation: {e}")
            return False
        except Exception as e:
            print(f"Confirmation error: {e}")
            return False
    
    def request_password_reset(self, email):
        """Request password reset"""
        if not self.csrf_token:
            self.get_csrf_token()
        
        data = {
            'email': email,
            'csrf_token': self.csrf_token
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/cgi-bin/reset-request.py",
                data=data
            )
            return response.status_code == 200 and ('reset link' in response.text.lower() or 'password reset' in response.text.lower())
        except:
            return False
    
    def reset_password(self, token, new_password):
        """Complete password reset"""
        if not self.csrf_token:
            self.get_csrf_token()
        
        data = {
            'token': token,
            'password': new_password,
            'confirm_password': new_password,
            'csrf_token': self.csrf_token
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/cgi-bin/reset-password.py",
                data=data
            )
            return response.status_code == 200 and 'password has been reset' in response.text.lower()
        except:
            return False
    
    def access_portal(self):
        """Try to access protected portal area"""
        try:
            response = self.session.get(
                f"{self.base_url}/portal/",
                allow_redirects=False
            )
            # 200 means we got in, 302 redirect means we need auth
            return response.status_code == 200
        except:
            return False
    
    def logout(self):
        """Logout current session"""
        try:
            response = self.session.get(f"{self.base_url}/cgi-bin/logout.py")
            return response.status_code == 200
        except:
            return False