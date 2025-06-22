#!/data/.venv/bin/python3
import cgi
import os
import sys
import hashlib
import secrets
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from session import SessionManager
from csrf import CSRFProtection
from user_db import UserDatabase
from rate_limit import RateLimiter

def main():
    # Set content type
    print("Content-Type: text/html\n")
    
    # Parse form data
    form = cgi.FieldStorage()
    
    # Initialize components
    session_mgr = SessionManager()
    csrf = CSRFProtection()
    user_db = UserDatabase()
    rate_limiter = RateLimiter()
    
    # Get client info
    client_ip = os.environ.get('REMOTE_ADDR', '')
    user_agent = os.environ.get('HTTP_USER_AGENT', '')
    
    # Check rate limit
    if not rate_limiter.check_limit(client_ip, 'login'):
        print_error("Too many login attempts. Please try again later.")
        return
    
    # Validate CSRF token
    csrf_token = form.getvalue('csrf_token', '')
    if not csrf.validate_token(csrf_token):
        print_error("Invalid security token. Please refresh and try again.")
        return
    
    # Get credentials
    username = form.getvalue('username', '').strip()
    password = form.getvalue('password', '')
    domain = form.getvalue('domain', 'lab.sethlakowske.com')
    
    # Validate input
    if not username or not password:
        print_error("Username and password are required.")
        return
    
    # Construct email if needed
    if '@' not in username:
        email = f"{username}@{domain}"
    else:
        email = username
    
    # Authenticate user
    if user_db.authenticate(email, password):
        # Create session
        session_id = session_mgr.create_session(email, client_ip, user_agent)
        
        # Set session cookie
        print(f"Set-Cookie: session_id={session_id}; Path=/; HttpOnly; Secure; SameSite=Strict")
        
        # Log successful login
        log_auth_event('login_success', email, client_ip)
        
        # Redirect to portal
        redirect_url = form.getvalue('redirect', '/portal/')
        print(f'<meta http-equiv="refresh" content="0;url={redirect_url}">')
        print("<html><body>Login successful. Redirecting...</body></html>")
    else:
        # Log failed attempt
        log_auth_event('login_failed', email, client_ip)
        rate_limiter.record_attempt(client_ip, 'login')
        
        print_error("Invalid username or password.")

def print_error(message):
    """Print error page"""
    print(f"""
    <html>
    <head>
        <title>Login Error</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Login Error</h1>
            <p class="error">{message}</p>
            <a href="/auth/login.html">Back to Login</a>
        </div>
    </body>
    </html>
    """)

def log_auth_event(event_type, email, ip_address):
    """Log authentication events"""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"[{timestamp}] [{event_type.upper()}] User: {email}, IP: {ip_address}"
    
    # Write to auth log
    log_dir = Path("/data/logs/apache")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    with open(log_dir / "auth.log", "a") as f:
        f.write(log_entry + "\n")

if __name__ == "__main__":
    main()