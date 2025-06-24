#!/data/.venv/bin/python3
import cgi
import os
import sys
import secrets
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from csrf import CSRFProtection
from user_db import UserDatabase
from email_sender import EmailSender
from rate_limit import RateLimiter

def main():
    print("Content-Type: text/html\n")
    
    form = cgi.FieldStorage()
    
    # Initialize components
    csrf = CSRFProtection()
    user_db = UserDatabase()
    email_sender = EmailSender()
    rate_limiter = RateLimiter()
    
    # Get client info
    client_ip = os.environ.get('REMOTE_ADDR', '')
    
    # Check rate limit
    if not rate_limiter.check_limit(client_ip, 'reset'):
        print_error("Too many password reset attempts. Please try again later.")
        return
    
    # Validate CSRF
    if not csrf.validate_token(form.getvalue('csrf_token', '')):
        print_error("Invalid security token.")
        return
    
    # Get email
    email = form.getvalue('email', '').strip().lower()
    
    if not email:
        print_error("Email address is required.")
        return
    
    # Check if user exists
    user_info = user_db.get_user_info(email)
    
    if user_info:
        # Generate reset token
        token = secrets.token_urlsafe(32)
        
        # Create pending reset
        pending_data = {
            'token': token,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            'email': email,
            'username': user_info['username'],
            'ip_address': client_ip
        }
        
        # Save pending reset
        pending_dir = Path("/data/user-data/pending/resets")
        pending_dir.mkdir(parents=True, exist_ok=True)
        
        with open(pending_dir / f"{token}.yaml", "w") as f:
            yaml.dump(pending_data, f)
        
        # Send reset email
        domain = os.environ.get('DOMAIN', 'localhost')
        reset_url = f"https://{domain}/auth/reset-password.html?token={token}"
        email_sent = email_sender.send_reset_email(email, user_info['username'], reset_url)
        
        if email_sent:
            # Log reset request
            log_auth_event('password_reset_requested', email, client_ip)
        
        # Record attempt regardless
        rate_limiter.record_attempt(client_ip, 'reset')
    
    # Always show success message (don't reveal if email exists)
    print_success("If an account exists with this email address, you will receive a password reset link shortly.")

def print_error(message):
    """Print error page"""
    print(f"""
    <html>
    <head>
        <title>Password Reset Error</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Password Reset Error</h1>
            <p class="error">{message}</p>
            <a href="/auth/forgot-password.html">Try Again</a> |
            <a href="/auth/login.html">Back to Login</a>
        </div>
    </body>
    </html>
    """)

def print_success(message):
    """Print success page"""
    print(f"""
    <html>
    <head>
        <title>Password Reset Requested</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Password Reset Requested</h1>
            <p class="success">{message}</p>
            <p>Please check your email for further instructions.</p>
            <p>The reset link will expire in 1 hour.</p>
            <a href="/auth/login.html">Back to Login</a>
        </div>
    </body>
    </html>
    """)

def log_auth_event(event_type, email, ip_address):
    """Log authentication events"""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"[{timestamp}] [{event_type.upper()}] User: {email}, IP: {ip_address}"
    
    log_dir = Path("/data/logs/apache")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    with open(log_dir / "auth.log", "a") as f:
        f.write(log_entry + "\n")

if __name__ == "__main__":
    main()