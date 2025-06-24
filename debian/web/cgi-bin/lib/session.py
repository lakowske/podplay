import os
import secrets
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

class SessionManager:
    def __init__(self):
        self.session_dir = Path("/data/user-data/pending/sessions")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_duration = timedelta(hours=12)
    
    def create_session(self, user_email, ip_address, user_agent):
        """Create a new session"""
        session_id = f"sess_{secrets.token_hex(16)}"
        csrf_token = secrets.token_urlsafe(32)
        
        session_data = {
            'session_id': session_id,
            'user_email': user_email,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'expires_at': (datetime.now(timezone.utc) + self.session_duration).isoformat(),
            'last_activity': datetime.now(timezone.utc).isoformat(),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'csrf_token': csrf_token
        }
        
        # Save session
        with open(self.session_dir / f"{session_id}.yaml", "w") as f:
            yaml.dump(session_data, f)
        
        return session_id
    
    def get_session(self, session_id):
        """Get session data"""
        if not session_id or not session_id.startswith('sess_'):
            return None
            
        session_file = self.session_dir / f"{session_id}.yaml"
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, "r") as f:
                session_data = yaml.safe_load(f)
            
            # Check expiration
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if datetime.now(timezone.utc) > expires_at:
                self.destroy_session(session_id)
                return None
            
            # Update last activity
            session_data['last_activity'] = datetime.now(timezone.utc).isoformat()
            
            with open(session_file, "w") as f:
                yaml.dump(session_data, f)
            
            return session_data
        except Exception:
            return None
    
    def destroy_session(self, session_id):
        """Destroy a session"""
        if not session_id or not session_id.startswith('sess_'):
            return
            
        session_file = self.session_dir / f"{session_id}.yaml"
        if session_file.exists():
            session_file.unlink()
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        for session_file in self.session_dir.glob("sess_*.yaml"):
            try:
                with open(session_file, "r") as f:
                    session_data = yaml.safe_load(f)
                
                expires_at = datetime.fromisoformat(session_data['expires_at'])
                if datetime.now(timezone.utc) > expires_at:
                    session_file.unlink()
            except:
                # Remove corrupted session files
                session_file.unlink()
    
    def get_session_from_cookie(self, cookie_string):
        """Extract session ID from cookie string"""
        if not cookie_string:
            return None
            
        cookies = {}
        for cookie in cookie_string.split(';'):
            parts = cookie.strip().split('=', 1)
            if len(parts) == 2:
                key, value = parts
                cookies[key.strip()] = value.strip()
        
        return cookies.get('session_id')