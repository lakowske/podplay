#!/data/.venv/bin/python3
import cgi
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from session import SessionManager

def main():
    # Get session ID from cookie
    cookie_string = os.environ.get('HTTP_COOKIE', '')
    session_mgr = SessionManager()
    session_id = session_mgr.get_session_from_cookie(cookie_string)
    
    # Get session data for logging
    session_data = None
    if session_id:
        session_data = session_mgr.get_session(session_id)
    
    # Set content type and clear session cookie
    print("Content-Type: text/html")
    print("Set-Cookie: session_id=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0")
    print()  # Empty line required after headers
    
    # Destroy session
    if session_id:
        session_mgr.destroy_session(session_id)
    
    # Log logout
    if session_data:
        log_auth_event('logout', session_data['user_email'], 
                      os.environ.get('REMOTE_ADDR', ''))
    
    # Show logout page
    print("""
    <html>
    <head>
        <title>Logged Out - PodPlay</title>
        <link rel="stylesheet" href="/static/css/auth.css">
    </head>
    <body>
        <div class="auth-container">
            <h1>Logged Out</h1>
            <p class="success">You have been successfully logged out.</p>
            <p>Thank you for using PodPlay!</p>
            <a href="/auth/login.html" class="btn btn-primary">Login Again</a>
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