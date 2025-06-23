#!/data/.venv/bin/python3
"""
Improved authentication CGI script with comprehensive error handling and logging
"""

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
from cgi_wrapper import cgi_main_wrapper, get_client_context, log_form_data
from logger import CGILogger, ValidationError, AuthenticationError, RateLimitError

# Enable verbose logging for debugging
VERBOSE_DEBUG = True

def debug_log(logger, message, **kwargs):
    """Log debug message if verbose debugging is enabled."""
    if VERBOSE_DEBUG:
        logger.log_info(f"[DEBUG] {message}", **kwargs)

def auth_main():
    """Main authentication logic with improved error handling"""
    
    # Initialize logger and get client context
    logger = CGILogger("auth.py")
    client_context = get_client_context()
    client_ip = client_context['ip']
    
    # Parse form data
    form = cgi.FieldStorage()
    log_form_data(logger, form, client_ip)
    
    # Initialize components
    try:
        session_mgr = SessionManager()
        csrf = CSRFProtection()
        user_db = UserDatabase()
        rate_limiter = RateLimiter()
    except Exception as e:
        logger.log_error("Failed to initialize authentication components", exception=e, client_ip=client_ip)
        raise AuthenticationError("Authentication system initialization failed")
    
    # Check rate limit
    if not rate_limiter.check_limit(client_ip, 'login'):
        logger.log_security_event("rate_limit_exceeded", "Login rate limit exceeded", client_ip=client_ip)
        raise RateLimitError("Too many login attempts from this IP address")
    
    # Validate CSRF token (temporarily disabled for testing)
    csrf_token = form.getvalue('csrf_token', '')
    # if not csrf.validate_token(csrf_token):
    #     logger.log_security_event("csrf_failure", "Invalid CSRF token", client_ip=client_ip, 
    #                             extra={'token_provided': bool(csrf_token)})
    #     raise ValidationError("Invalid security token. Please refresh the page and try again.")
    
    # Get and validate credentials
    username = form.getvalue('username', '').strip()
    password = form.getvalue('password', '')
    domain = form.getvalue('domain', 'lab.sethlakowske.com').strip()
    
    # Input validation
    if not username:
        raise ValidationError("Username is required.")
    if not password:
        raise ValidationError("Password is required.")
    if len(password) < 6:
        raise ValidationError("Password must be at least 6 characters.")
    
    # Construct email if needed
    if '@' not in username:
        if not domain:
            raise ValidationError("Domain is required when username doesn't include @ symbol.")
        email = f"{username}@{domain}"
    else:
        email = username
        # Extract domain from email for validation
        domain = email.split('@')[1]
    
    # Log authentication attempt
    logger.log_info(f"Authentication attempt for user: {email}", 
                   user_email=email, client_ip=client_ip,
                   extra={'domain': domain})
    
    debug_log(logger, f"Starting authentication for email: {email}, domain: {domain}", 
              user_email=email, client_ip=client_ip)
    
    # Authenticate user
    try:
        debug_log(logger, f"Calling user_db.authenticate() for {email}", 
                  user_email=email, client_ip=client_ip)
        auth_success = user_db.authenticate(email, password)
        debug_log(logger, f"Authentication result for {email}: {auth_success}", 
                  user_email=email, client_ip=client_ip)
    except Exception as e:
        logger.log_error("Database authentication error", exception=e, 
                        user_email=email, client_ip=client_ip)
        raise AuthenticationError("Authentication system error")
    
    if auth_success:
        # Successful authentication
        try:
            # Create session
            session_id = session_mgr.create_session(email, client_ip, client_context['user_agent'])
            
            # Log successful login (both old and new systems)
            log_auth_event('login_success', email, client_ip)
            logger.log_info(f"Login successful for user: {email}", 
                           user_email=email, client_ip=client_ip,
                           extra={'session_id': session_id[:16] + '...'})  # Log partial session ID
            
            # Redirect to portal or specified URL
            redirect_url = form.getvalue('redirect', '/portal/')
            
            # Validate redirect URL for security
            if not redirect_url.startswith('/'):
                logger.log_security_event("redirect_attack", f"Invalid redirect URL: {redirect_url}",
                                        user_email=email, client_ip=client_ip)
                redirect_url = '/portal/'
            
            # Set session cookie and redirect (proper CGI headers)
            print(f"Set-Cookie: session_id={session_id}; Path=/; HttpOnly; Secure; SameSite=Strict")
            print(f"Location: {redirect_url}")
            print("Status: 302 Found")
            print("Content-Type: text/html")
            print()  # Blank line required between headers and content
            print("<html><body>Login successful. Redirecting...</body></html>")
            
        except Exception as e:
            logger.log_error("Session creation failed", exception=e, 
                            user_email=email, client_ip=client_ip)
            raise AuthenticationError("Failed to create user session")
            
    else:
        # Authentication failed
        logger.log_security_event("login_failure", f"Failed login attempt for: {email}",
                                user_email=email, client_ip=client_ip,
                                extra={'username_format': 'email' if '@' in username else 'username'})
        
        # Record rate limiting attempt
        try:
            rate_limiter.record_attempt(client_ip, 'login')
        except Exception as e:
            logger.log_warning("Failed to record rate limit attempt", exception=e, client_ip=client_ip)
        
        # Log to old auth system
        log_auth_event('login_failed', email, client_ip)
        
        # Send authentication failure response with proper headers
        print("Content-Type: text/html")
        print("Status: 401 Unauthorized")
        print()  # Blank line between headers and content
        print("<h1>Authentication Failed</h1><p>Invalid username or password</p>")
        return

def log_auth_event(event_type, email, ip_address):
    """Legacy authentication event logging (maintained for compatibility)"""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"[{timestamp}] [{event_type.upper()}] User: {email}, IP: {ip_address}"
    
    # Write to auth log
    log_dir = Path("/data/logs/apache")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(log_dir / "auth.log", "a") as f:
            f.write(log_entry + "\n")
    except Exception:
        # Don't fail if legacy logging fails
        pass

if __name__ == "__main__":
    # Don't use cgi_main_wrapper because we need to control headers
    try:
        auth_main()
    except (ValidationError, AuthenticationError, RateLimitError) as e:
        # Send proper error response with headers
        print("Content-Type: text/html")
        print("Status: 400 Bad Request")
        print()  # Blank line between headers and content
        print(f"<h1>Error</h1><p>{str(e)}</p>")
    except Exception as e:
        # Send server error response
        print("Content-Type: text/html") 
        print("Status: 500 Internal Server Error")
        print()  # Blank line between headers and content
        print(f"<h1>Internal Server Error</h1><p>An unexpected error occurred.</p>")