import secrets
import hmac
import hashlib
import os
from datetime import datetime, timedelta, timezone

class CSRFProtection:
    def __init__(self):
        # Use a secret key from environment or generate one
        self.secret_key = os.environ.get('CSRF_SECRET_KEY', 'default-secret-key-change-in-production').encode()
        self.token_lifetime = timedelta(hours=4)
    
    def generate_token(self):
        """Generate a new CSRF token"""
        # Create token with timestamp
        timestamp = int(datetime.now(timezone.utc).timestamp())
        nonce = secrets.token_hex(16)
        token_data = f"{timestamp}:{nonce}"
        
        # Create HMAC signature
        signature = hmac.new(
            self.secret_key,
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Return token
        return f"{token_data}:{signature}"
    
    def validate_token(self, token):
        """Validate a CSRF token"""
        if not token:
            return False
        
        try:
            # Split token
            parts = token.split(':')
            if len(parts) != 3:
                return False
            
            timestamp_str, nonce, signature = parts
            
            # Verify signature
            token_data = f"{timestamp_str}:{nonce}"
            expected_signature = hmac.new(
                self.secret_key,
                token_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                return False
            
            # Check timestamp
            timestamp = int(timestamp_str)
            token_time = datetime.fromtimestamp(timestamp, timezone.utc)
            
            if datetime.now(timezone.utc) - token_time > self.token_lifetime:
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_token_for_session(self, session_data):
        """Get CSRF token from session or generate new one"""
        if session_data and 'csrf_token' in session_data:
            return session_data['csrf_token']
        return self.generate_token()
    
    @staticmethod
    def inject_token_into_html(html_content, token):
        """Replace {CSRF_TOKEN} placeholder in HTML with actual token"""
        return html_content.replace('{CSRF_TOKEN}', token)