#!/data/.venv/bin/python3
"""
Improved confirmation CGI script with comprehensive error handling and mail domain user activation
"""

import cgi
import os
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from user_db import UserDatabase
from cgi_wrapper import cgi_main_wrapper, get_client_context
from logger import CGILogger, ValidationError, ConfigurationError


def confirm_main():
    """Main confirmation logic with improved error handling"""
    
    # Initialize logger and get client context
    logger = CGILogger("confirm.py")
    client_context = get_client_context()
    client_ip = client_context['ip']
    
    # Parse form data
    form = cgi.FieldStorage()
    
    # Get token
    token = form.getvalue('token', '').strip()
    
    if not token:
        logger.log_warning("Confirmation attempt without token", client_ip=client_ip)
        raise ValidationError("Missing confirmation token.")
    
    # Load pending registration
    pending_dir = Path("/data/user-data/pending/registrations")
    token_file = pending_dir / f"{token}.yaml"
    
    if not token_file.exists():
        logger.log_warning(
            f"Invalid confirmation token attempted: {token[:16]}...",
            client_ip=client_ip
        )
        raise ValidationError("Invalid or expired confirmation token.")
    
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            pending_data = yaml.safe_load(f)
        
        # Check expiration
        expires_at = datetime.fromisoformat(pending_data['expires_at'])
        if datetime.now(timezone.utc) > expires_at:
            token_file.unlink()  # Clean up expired token
            logger.log_warning(
                f"Expired confirmation token: {token[:16]}...",
                client_ip=client_ip
            )
            raise ValidationError(
                "Confirmation token has expired. Please register again."
            )
        
        # Initialize user database
        try:
            user_db = UserDatabase()
        except Exception as e:
            logger.log_error(
                "Failed to initialize user database",
                exception=e,
                client_ip=client_ip
            )
            raise ConfigurationError("User system initialization failed") from e
        
        user_data = pending_data['user_data']
        user_email = user_data['email']
        user_domain = user_email.split('@')[1]
        mail_domain = "lab.sethlakowske.com"
        
        logger.log_info(
            f"Processing confirmation for user: {user_email}",
            user_email=user_email,
            client_ip=client_ip
        )
        
        if user_domain == mail_domain:
            # For mail domain users: user already exists (inactive),
            # just enable them
            logger.log_info(
                f"Activating existing mail domain user: {user_email}",
                user_email=user_email,
                client_ip=client_ip
            )
            
            try:
                success = user_db.enable_user(user_email)
                if not success:
                    logger.log_error(
                        f"Failed to enable mail domain user: {user_email}",
                        user_email=user_email,
                        client_ip=client_ip
                    )
                    raise ConfigurationError(
                        "Failed to activate user account"
                    )
                
                logger.log_info(
                    f"Successfully activated mail domain user: {user_email}",
                    user_email=user_email,
                    client_ip=client_ip
                )
                
            except Exception as e:
                logger.log_error(
                    "Failed to enable mail domain user",
                    exception=e,
                    user_email=user_email,
                    client_ip=client_ip
                )
                raise ConfigurationError(
                    "Failed to activate user account"
                ) from e
        
        else:
            # For external domain users: add user to system
            logger.log_info(
                f"Adding external domain user: {user_email}",
                user_email=user_email,
                client_ip=client_ip
            )
            
            # Update password to use the hash directly
            user_data['password'] = user_data.pop('password_hash')
            # External users start enabled after confirmation
            user_data['enabled'] = True
            
            try:
                user_db.add_user(user_data)
                logger.log_info(
                    f"Successfully added external domain user: {user_email}",
                    user_email=user_email,
                    client_ip=client_ip
                )
                
            except Exception as e:
                logger.log_error(
                    "Failed to add external domain user",
                    exception=e,
                    user_email=user_email,
                    client_ip=client_ip
                )
                raise ConfigurationError(
                    "Failed to create user account"
                ) from e
        
        # Remove pending registration
        try:
            token_file.unlink()
        except Exception as e:
            logger.log_warning(
                "Failed to remove pending registration file",
                exception=e,
                user_email=user_email,
                client_ip=client_ip
            )
        
        # Log confirmation
        log_auth_event(
            'registration_confirmed',
            user_email,
            pending_data.get('ip_address', client_ip)
        )
        logger.log_info(
            f"Account confirmation completed for: {user_email}",
            user_email=user_email,
            client_ip=client_ip
        )
        
        print_success(f"Account confirmed for {user_email}!")
        
    except ValidationError:
        # Re-raise validation errors (already logged by wrapper)
        raise
    except ConfigurationError:
        # Re-raise configuration errors (already logged by wrapper)
        raise
    except Exception as e:
        logger.log_error(
            "Unexpected error during confirmation",
            exception=e,
            client_ip=client_ip
        )
        raise ConfigurationError(
            "An unexpected error occurred during confirmation"
        ) from e


def print_success(message):
    """Print success page"""
    print(f"""<!DOCTYPE html>
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
        <div class="success-actions">
            <a href="/auth/login.html" class="btn btn-primary">Go to Login</a>
        </div>
    </div>
</body>
</html>""")


def log_auth_event(event_type, email, ip_address):
    """Legacy authentication event logging (maintained for compatibility)"""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = (f"[{timestamp}] [{event_type.upper()}] "
                 f"User: {email}, IP: {ip_address}")
    
    log_dir = Path("/data/logs/apache")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(log_dir / "auth.log", "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception:
        # Don't fail if legacy logging fails
        pass


if __name__ == "__main__":
    cgi_main_wrapper(confirm_main, "confirm.py")