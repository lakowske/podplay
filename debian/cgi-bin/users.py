#!/usr/bin/env python3
import cgi
import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from session import SessionManager
from csrf import CSRFProtection
from user_db import UserDatabase

def log_operation(operation, details):
    """Log admin operations to auth log."""
    timestamp = datetime.now(timezone.utc).isoformat()
    client_ip = os.environ.get('REMOTE_ADDR', 'unknown')
    session_mgr = SessionManager()
    session_id = get_session_id()
    session = session_mgr.get_session(session_id) if session_id else None
    user_email = session.get('user_email', 'unknown') if session else 'unknown'
    
    log_entry = f"[{timestamp}] [{operation.upper()}] Admin: {user_email}, Target: {details}, IP: {client_ip}"
    
    log_dir = Path("/data/logs/apache")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    with open(log_dir / "auth.log", "a") as f:
        f.write(log_entry + "\n")

def get_session_id():
    """Extract session ID from cookies."""
    if 'HTTP_COOKIE' in os.environ:
        cookies = os.environ['HTTP_COOKIE'].split('; ')
        for cookie in cookies:
            if cookie.startswith('session_id='):
                return cookie.split('=')[1]
    return None

def check_admin_permission():
    """Check if user has admin permissions."""
    session_mgr = SessionManager()
    session_id = get_session_id()
    
    if not session_id:
        return False
    
    session = session_mgr.get_session(session_id)
    if not session:
        return False
    
    # Check if user is admin
    user_email = session.get('user_email', '')
    # Simple check - in production, check against role database
    return user_email.startswith('admin@')

def list_users(domain=None):
    """List all users."""
    user_db = UserDatabase()
    users = []
    
    # Load user configuration
    config_path = Path("/data/user-data/config/users.yaml")
    if not config_path.exists():
        return users
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Process domains
    for domain_config in config.get('domains', []):
        if domain and domain_config['name'] != domain:
            continue
        
        for user in domain_config.get('users', []):
            user_info = {
                'username': user['username'],
                'domain': domain_config['name'],
                'email': f"{user['username']}@{domain_config['name']}",
                'quota': user.get('quota', 'default'),
                'enabled': user.get('enabled', True),
                'services': user.get('services', ['mail'])
            }
            users.append(user_info)
    
    return users

def create_user(username, email, password, quota='500M'):
    """Create a new user."""
    # Use user_manager.py
    cmd = [
        "/data/src/user_manager.py",
        "--add-user",
        "--user", username,
        "--email", email,
        "--password", password,
        "--quota", quota
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_operation('USER_CREATED', email)
        return True
    except subprocess.CalledProcessError:
        return False

def delete_user(email):
    """Delete a user."""
    cmd = [
        "/data/src/user_manager.py",
        "--remove-user",
        "--email", email
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        log_operation('USER_DELETED', email)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    """Main CGI handler."""
    # Check admin permission
    if not check_admin_permission():
        print("Status: 403 Forbidden")
        print("Content-Type: text/html\n")
        print("<h1>Access Denied</h1>")
        print("<p>Admin privileges required</p>")
        return
    
    # Parse request
    form = cgi.FieldStorage()
    action = form.getvalue('action', 'list')
    
    # Handle JSON responses for CLI
    accept_header = os.environ.get('HTTP_ACCEPT', '')
    json_response = 'application/json' in accept_header
    
    if action == 'list':
        domain = form.getvalue('domain')
        users = list_users(domain)
        
        if json_response:
            print("Content-Type: application/json\n")
            print(json.dumps(users))
        else:
            print("Content-Type: text/html\n")
            print("<h1>User List</h1>")
            print("<table border='1'>")
            print("<tr><th>Email</th><th>Quota</th><th>Services</th><th>Enabled</th></tr>")
            for user in users:
                enabled = '✓' if user['enabled'] else '✗'
                services = ', '.join(user['services'])
                print(f"<tr><td>{user['email']}</td><td>{user['quota']}</td>"
                      f"<td>{services}</td><td>{enabled}</td></tr>")
            print("</table>")
    
    elif action == 'create':
        # Validate CSRF token
        csrf = CSRFProtection()
        if not csrf.validate_token(form.getvalue('csrf_token', '')):
            print("Status: 403 Forbidden")
            print("Content-Type: text/html\n")
            print("<h1>Invalid CSRF Token</h1>")
            return
        
        username = form.getvalue('username')
        email = form.getvalue('email')
        password = form.getvalue('password')
        quota = form.getvalue('quota', '500M')
        
        if create_user(username, email, password, quota):
            print("Content-Type: text/html\n")
            print("<h1>User Created</h1>")
            print(f"<p>User {email} created successfully</p>")
        else:
            print("Status: 500 Internal Server Error")
            print("Content-Type: text/html\n")
            print("<h1>Error</h1>")
            print("<p>Failed to create user</p>")
    
    elif action == 'delete':
        # Validate CSRF token
        csrf = CSRFProtection()
        if not csrf.validate_token(form.getvalue('csrf_token', '')):
            print("Status: 403 Forbidden")
            print("Content-Type: text/html\n")
            print("<h1>Invalid CSRF Token</h1>")
            return
        
        email = form.getvalue('email')
        
        if delete_user(email):
            print("Content-Type: text/html\n")
            print("<h1>User Deleted</h1>")
            print(f"<p>User {email} deleted successfully</p>")
        else:
            print("Status: 500 Internal Server Error")
            print("Content-Type: text/html\n")
            print("<h1>Error</h1>")
            print("<p>Failed to delete user</p>")

if __name__ == "__main__":
    main()