#!/data/.venv/bin/python3
import cgi
import os
import sys
import secrets
import yaml
import re
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
    user_agent = os.environ.get('HTTP_USER_AGENT', '')
    
    # Check rate limit
    if not rate_limiter.check_limit(client_ip, 'register'):
        print_error("Too many registration attempts. Please try again later.")
        return
    
    # Validate CSRF
    if not csrf.validate_token(form.getvalue('csrf_token', '')):
        print_error("Invalid security token.")
        return
    
    # Get form data
    username = form.getvalue('username', '').strip().lower()
    email = form.getvalue('email', '').strip().lower()
    password = form.getvalue('password', '')
    confirm_password = form.getvalue('confirm_password', '')
    
    # Validate input
    errors = validate_registration(username, email, password, confirm_password)
    if errors:
        print_error("<br>".join(errors))
        return
    
    # Check if user exists
    if user_db.user_exists(email):
        print_error("An account with this email already exists.")
        return
    
    # Generate confirmation token
    token = secrets.token_urlsafe(32)
    
    # Create pending registration
    pending_data = {
        'token': token,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        'user_data': {
            'username': username,
            'email': email,
            'password_hash': user_db.hash_password(password),
            'domain': email.split('@')[1],
            'quota': '500M',
            'services': ['mail', 'webdav']
        },
        'ip_address': client_ip,
        'user_agent': user_agent
    }
    
    # Save pending registration
    pending_dir = Path("/data/user-data/pending/registrations")
    pending_dir.mkdir(parents=True, exist_ok=True)
    
    with open(pending_dir / f"{token}.yaml", "w") as f:
        yaml.dump(pending_data, f)
    
    # Send confirmation email
    confirmation_url = f"https://lab.sethlakowske.com/cgi-bin/confirm.py?token={token}"
    email_sent = email_sender.send_confirmation_email(email, username, confirmation_url)
    
    if email_sent:
        # Log registration attempt
        log_auth_event('registration_pending', email, client_ip)
        
        print_success("Registration successful! Please check your email to confirm your account.")
    else:
        print_error("Failed to send confirmation email. Please try again later.")

def validate_registration(username, email, password, confirm_password):
    """Validate registration input"""
    errors = []
    
    # Username validation
    if not username:
        errors.append("Username is required")
    elif not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        errors.append("Username can only contain letters, numbers, dots, dashes and underscores")
    elif len(username) < 3:
        errors.append("Username must be at least 3 characters")
    
    # Email validation
    if not email:
        errors.append("Email is required")
    elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        errors.append("Invalid email address")
    
    # Password validation
    if not password:
        errors.append("Password is required")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters")
    elif password != confirm_password:
        errors.append("Passwords do not match")
    
    return errors

def print_error(message):
    """Print error page"""
    print(f"""
    <html>
    <head>
        <title>Registration Error</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Registration Error</h1>
            <p class="error">{message}</p>
            <a href="/auth/register.html">Back to Registration</a>
        </div>
    </body>
    </html>
    """)

def print_success(message):
    """Print success page"""
    print(f"""
    <html>
    <head>
        <title>Registration Successful</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Registration Successful</h1>
            <p class="success">{message}</p>
            <p>You will receive an email shortly with a confirmation link.</p>
            <p>The link will expire in 1 hour.</p>
            <a href="/auth/login.html">Go to Login</a>
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