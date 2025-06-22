#!/data/.venv/bin/python3
import cgi
import os
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from user_db import UserDatabase

def main():
    print("Content-Type: text/html\n")
    
    form = cgi.FieldStorage()
    
    # Get token
    token = form.getvalue('token', '')
    
    if not token:
        print_error("Missing confirmation token.")
        return
    
    # Load pending registration
    pending_dir = Path("/data/user-data/pending/registrations")
    token_file = pending_dir / f"{token}.yaml"
    
    if not token_file.exists():
        print_error("Invalid or expired confirmation token.")
        return
    
    try:
        with open(token_file, "r") as f:
            pending_data = yaml.safe_load(f)
        
        # Check expiration
        expires_at = datetime.fromisoformat(pending_data['expires_at'])
        if datetime.now(timezone.utc) > expires_at:
            token_file.unlink()  # Clean up expired token
            print_error("Confirmation token has expired. Please register again.")
            return
        
        # Add user to system
        user_db = UserDatabase()
        user_data = pending_data['user_data']
        
        # Update password to use the hash directly
        user_data['password'] = user_data.pop('password_hash')
        
        # Add user
        user_db.add_user(user_data)
        
        # Remove pending registration
        token_file.unlink()
        
        # Log confirmation
        log_auth_event('registration_confirmed', user_data['email'], pending_data['ip_address'])
        
        print_success(f"Account confirmed for {user_data['email']}!")
        
    except Exception as e:
        print_error(f"Error confirming account: {str(e)}")

def print_error(message):
    """Print error page"""
    print(f"""
    <html>
    <head>
        <title>Confirmation Error</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Confirmation Error</h1>
            <p class="error">{message}</p>
            <a href="/auth/register.html">Register Again</a> |
            <a href="/auth/login.html">Go to Login</a>
        </div>
    </body>
    </html>
    """)

def print_success(message):
    """Print success page"""
    print(f"""
    <html>
    <head>
        <title>Account Confirmed</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Account Confirmed!</h1>
            <p class="success">{message}</p>
            <p>You can now log in with your username and password.</p>
            <a href="/auth/login.html" class="btn btn-primary">Go to Login</a>
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