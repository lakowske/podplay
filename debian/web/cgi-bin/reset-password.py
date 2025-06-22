#!/data/.venv/bin/python3
import cgi
import os
import sys
import yaml
import re
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from csrf import CSRFProtection
from user_db import UserDatabase

def main():
    print("Content-Type: text/html\n")
    
    form = cgi.FieldStorage()
    
    # Initialize components
    csrf = CSRFProtection()
    user_db = UserDatabase()
    
    # Validate CSRF
    if not csrf.validate_token(form.getvalue('csrf_token', '')):
        print_error("Invalid security token.")
        return
    
    # Get token and passwords
    token = form.getvalue('token', '')
    password = form.getvalue('password', '')
    confirm_password = form.getvalue('confirm_password', '')
    
    if not token:
        print_error("Missing reset token.")
        return
    
    if not password or not confirm_password:
        print_error("Password and confirmation are required.")
        return
    
    if password != confirm_password:
        print_error("Passwords do not match.")
        return
    
    # Validate password
    if len(password) < 8:
        print_error("Password must be at least 8 characters long.")
        return
    
    # Load pending reset
    pending_dir = Path("/data/user-data/pending/resets")
    token_file = pending_dir / f"{token}.yaml"
    
    if not token_file.exists():
        print_error("Invalid or expired reset token.")
        return
    
    try:
        with open(token_file, "r") as f:
            pending_data = yaml.safe_load(f)
        
        # Check expiration
        expires_at = datetime.fromisoformat(pending_data['expires_at'])
        if datetime.now(timezone.utc) > expires_at:
            token_file.unlink()  # Clean up expired token
            print_error("Reset token has expired. Please request a new password reset.")
            return
        
        # Update user password
        email = pending_data['email']
        password_hash = user_db.hash_password(password)
        
        if user_db.update_password(email, password_hash):
            # Remove pending reset
            token_file.unlink()
            
            # Log password change
            log_auth_event('password_changed', email, pending_data['ip_address'])
            
            print_success("Password has been successfully updated!")
        else:
            print_error("Failed to update password. Please try again.")
        
    except Exception as e:
        print_error(f"Error processing password reset: {str(e)}")

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
            <a href="/auth/forgot-password.html">Request New Reset</a> |
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
        <title>Password Reset Successful</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Password Reset Successful</h1>
            <p class="success">{message}</p>
            <p>You can now log in with your new password.</p>
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