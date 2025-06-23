#!/data/.venv/bin/python3

import cgi
import os
import sys
import secrets
import yaml
import re
import traceback
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] [REGISTER] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)

def safe_print_headers():
    """Safely print HTTP headers if not already printed"""
    try:
        print("Content-Type: text/html\n")
        sys.stdout.flush()
    except:
        pass

def safe_import_libraries():
    """Safely import required libraries with error handling"""
    try:
        # Add lib to path
        lib_path = os.path.join(os.path.dirname(__file__), 'lib')
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        
        # Try importing required modules
        from user_db import UserDatabase
        from email_sender import EmailSender
        
        logger.info("Successfully imported required libraries")
        return UserDatabase, EmailSender, None
        
    except ImportError as e:
        error_msg = f"Failed to import required libraries: {str(e)}"
        logger.error(error_msg)
        return None, None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error importing libraries: {str(e)}"
        logger.error(error_msg)
        return None, None, error_msg

# Initialize and print headers first
safe_print_headers()
logger.info("Registration script started")

# Try to import libraries
UserDatabase, EmailSender, import_error = safe_import_libraries()

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

def print_error(user_message, technical_details=None, error_code=None):
    """Print user-friendly error page without leaking technical details"""
    if technical_details:
        logger.error(f"Registration error ({error_code}): {technical_details}")
    
    # Sanitize user message to prevent HTML injection
    safe_message = user_message.replace('<', '&lt;').replace('>', '&gt;')
    
    print(f"""<!DOCTYPE html>
<html>
<head>
    <title>Registration Error</title>
    <link rel="stylesheet" href="/static/css/auth.css">
</head>
<body>
    <div class="auth-container">
        <h1>Registration Error</h1>
        <div class="error-message">
            <p class="error">{safe_message}</p>
        </div>
        <div class="error-actions">
            <a href="/auth/register.html" class="btn btn-primary">Try Again</a>
            <a href="/auth/login.html" class="btn btn-secondary">Login Instead</a>
        </div>
        <div class="help-text">
            <p>If you continue to experience problems, please contact support.</p>
        </div>
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

# Check for import errors first
if import_error:
    print_error(
        "Service temporarily unavailable. Please try again later.",
        technical_details=import_error,
        error_code="IMPORT_ERROR"
    )
    sys.exit(0)

def main():
    """Main registration logic with comprehensive error handling"""
    try:
        logger.info("Processing registration request")
        
        # Parse form data
        form = cgi.FieldStorage()
        
        # Get form data with logging
        username = form.getvalue('username', '').strip().lower()
        email = form.getvalue('email', '').strip().lower()
        password = form.getvalue('password', '')
        confirm_password = form.getvalue('confirm_password', '')
        
        logger.info(f"Registration attempt for username: {username}, email: {email}")
        
        # Validate input
        errors = validate_registration(username, email, password, confirm_password)
        if errors:
            error_msg = "; ".join(errors)
            print_error(
                "Please check your input and try again.",
                technical_details=f"Validation errors: {error_msg}",
                error_code="VALIDATION_ERROR"
            )
            return
        
        # Initialize components with error handling
        try:
            user_db = UserDatabase()
            email_sender = EmailSender()
            logger.info("Successfully initialized database and email components")
        except Exception as e:
            print_error(
                "Service temporarily unavailable. Please try again later.",
                technical_details=f"Component initialization failed: {str(e)}",
                error_code="INIT_ERROR"
            )
            return
        
        # Check if user exists
        try:
            if user_db.user_exists(email):
                print_error(
                    "An account with this email already exists.",
                    technical_details=f"Duplicate email: {email}",
                    error_code="DUPLICATE_USER"
                )
                return
        except Exception as e:
            print_error(
                "Unable to check existing users. Please try again later.",
                technical_details=f"User existence check failed: {str(e)}",
                error_code="DB_CHECK_ERROR"
            )
            return
        
        # Generate confirmation token
        token = secrets.token_urlsafe(32)
        logger.debug(f"Generated confirmation token for {email}")
        
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
        try:
            pending_dir = Path("/data/user-data/pending/registrations")
            pending_dir.mkdir(parents=True, exist_ok=True)
            
            with open(pending_dir / f"{token}.yaml", "w") as f:
                yaml.dump(pending_data, f)
            
            logger.info(f"Saved pending registration for {email}")
        except Exception as e:
            print_error(
                "Unable to save registration data. Please try again later.",
                technical_details=f"Pending registration save failed: {str(e)}",
                error_code="SAVE_ERROR"
            )
            return
        
        # Add user immediately but mark email as unconfirmed
        try:
            user_data = pending_data['user_data'].copy()
            user_data['enabled'] = True  # Always enabled
            user_data['email_confirmed'] = False  # Start unconfirmed
            user_data['password'] = user_data.pop('password_hash')  # Use correct key
            user_db.add_user(user_data)
            logger.info(f"Added user {email} to database (unconfirmed)")
        except Exception as e:
            print_error(
                "Unable to create user account. Please try again later.",
                technical_details=f"User creation failed: {str(e)}",
                error_code="USER_CREATE_ERROR"
            )
            return
        
        # Wait briefly for hot-reload to process the new user
        # With 200ms debounce, we wait a bit longer to ensure mail configs are updated
        try:
            logger.info("Waiting for mail system to process new user configuration")
            import time
            time.sleep(0.5)  # Wait 500ms for hot-reload to complete (200ms debounce + processing time)
            logger.info("Mail configuration wait completed")
        except Exception as e:
            logger.error(f"Error during mail config wait: {str(e)}")
            # Continue anyway - this is just a timing optimization
        
        # Send confirmation email
        confirmation_url = f"https://lab.sethlakowske.com/cgi-bin/confirm.py?token={token}"
        
        try:
            email_sent = email_sender.send_confirmation_email(email, username, confirmation_url)
            logger.info(f"Email send result for {email}: {email_sent}")
        except Exception as e:
            logger.error(f"Email sending exception for {email}: {str(e)}")
            email_sent = False
        
        if email_sent:
            logger.info(f"Registration completed successfully for {email}")
            print_success("Registration successful! Please check your email to confirm your account.")
        else:
            print_error(
                "Account created but confirmation email could not be sent. Please contact support.",
                technical_details=f"Email sending failed for {email}",
                error_code="EMAIL_SEND_ERROR"
            )
    
    except Exception as e:
        logger.error(f"Unexpected error in registration: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print_error(
            "An unexpected error occurred. Please try again later.",
            technical_details=f"Unexpected error: {str(e)}\nTraceback: {traceback.format_exc()}",
            error_code="UNEXPECTED_ERROR"
        )

# Execute main function
if __name__ == "__main__":
    main()