#!/data/.venv/bin/python3

print("Content-Type: text/html\n")

import cgi
import os
import sys
import secrets
import yaml
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from user_db import UserDatabase
from email_sender import EmailSender

def print_success(message):
    print(f"""<!DOCTYPE html>
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
    </div>
</body>
</html>""")

def print_error(message):
    print(f"""<!DOCTYPE html>
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
</html>""")

def validate_registration(username, email, password, confirm_password):
    errors = []
    
    if not username:
        errors.append("Username is required")
    elif len(username) < 3:
        errors.append("Username must be at least 3 characters")
    
    if not email:
        errors.append("Email is required")
    elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        errors.append("Invalid email address")
    
    if not password:
        errors.append("Password is required")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters")
    elif password != confirm_password:
        errors.append("Passwords do not match")
    
    return errors

try:
    form = cgi.FieldStorage()
    
    # Get form data
    username = form.getvalue('username', '').strip().lower()
    email = form.getvalue('email', '').strip().lower()
    password = form.getvalue('password', '')
    confirm_password = form.getvalue('confirm_password', '')
    
    # Validate input
    errors = validate_registration(username, email, password, confirm_password)
    if errors:
        print_error("\\n".join(errors))
        sys.exit(0)
    
    # Initialize components
    user_db = UserDatabase()
    email_sender = EmailSender()
    
    # Check if user exists
    if user_db.user_exists(email):
        print_error("An account with this email already exists.")
        sys.exit(0)
    
    # Generate confirmation token
    token = secrets.token_urlsafe(32)
    
    # Create pending registration data
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
        'ip_address': os.environ.get('REMOTE_ADDR', 'unknown'),
        'user_agent': os.environ.get('HTTP_USER_AGENT', 'unknown')
    }
    
    # Save pending registration
    pending_dir = Path("/data/user-data/pending/registrations")
    pending_dir.mkdir(parents=True, exist_ok=True)
    
    with open(pending_dir / f"{token}.yaml", "w") as f:
        yaml.dump(pending_data, f)
    
    # For all users: add them immediately but mark email as unconfirmed
    user_data = pending_data['user_data'].copy()
    user_data['enabled'] = True  # Always enabled
    user_data['email_confirmed'] = False  # Start unconfirmed
    user_data['password'] = user_data.pop('password_hash')  # Use correct key
    user_db.add_user(user_data)
    
    # Send confirmation email
    confirmation_url = f"https://lab.sethlakowske.com/cgi-bin/confirm.py?token={token}"
    
    try:
        email_sent = email_sender.send_confirmation_email(email, username, confirmation_url)
    except:
        email_sent = False
    
    if email_sent:
        print_success("Registration successful! Please check your email to confirm your account.")
    else:
        print_error("Failed to send confirmation email. Please try again later.")

except Exception as e:
    print_error(f"Registration failed: {str(e)}")