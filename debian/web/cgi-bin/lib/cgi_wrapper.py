#!/usr/bin/env python3
"""
CGI wrapper for comprehensive error handling and logging
"""

import os
import sys
import cgi
import traceback
from datetime import datetime

from logger import CGILogger, ValidationError, AuthenticationError, RateLimitError, ConfigurationError

def cgi_main_wrapper(main_func, script_name):
    """
    Wrapper for CGI main functions with comprehensive error handling
    
    Args:
        main_func: The main function to execute
        script_name: Name of the CGI script for logging
    """
    # Set content type FIRST (before ANY other output)
    print("Content-Type: text/html\n")
    
    logger = CGILogger(script_name)
    
    try:
        # Get client info for logging context
        client_ip = os.environ.get('REMOTE_ADDR', 'unknown')
        user_agent = os.environ.get('HTTP_USER_AGENT', 'unknown')
        request_method = os.environ.get('REQUEST_METHOD', 'unknown')
        query_string = os.environ.get('QUERY_STRING', '')
        
        # Log request start
        request_info = {
            'method': request_method,
            'user_agent': user_agent,
            'query_string': query_string
        }
        logger.log_info(f"Request started", client_ip=client_ip, extra=request_info)
        
        # Execute main function
        result = main_func()
        
        # Ensure output is flushed
        import sys
        sys.stdout.flush()
        
        # Log successful completion
        logger.log_info(f"Request completed successfully", client_ip=client_ip)
        return result
        
    except ValidationError as e:
        # User input errors - safe to show details to user
        logger.log_warning(f"Validation error: {e}", client_ip=client_ip)
        print_user_error("Input Validation Error", str(e))
        
    except AuthenticationError as e:
        # Auth failures - log details but show generic message
        logger.log_security_event("auth_failure", f"Authentication error: {e}", client_ip=client_ip)
        print_user_error("Authentication Error", "Authentication failed. Please check your credentials and try again.")
        
    except RateLimitError as e:
        # Rate limiting - log and show rate limit message
        logger.log_security_event("rate_limit", f"Rate limit exceeded: {e}", client_ip=client_ip)
        print_user_error("Rate Limit Exceeded", "Too many requests. Please wait and try again later.")
        
    except ConfigurationError as e:
        # System configuration issues - log details, show generic message
        logger.log_error(f"Configuration error: {e}", client_ip=client_ip)
        print_server_error("System configuration issue. Please contact support.")
        
    except Exception as e:
        # Unexpected errors - log everything, show generic message
        logger.log_error(f"Unexpected error in {script_name}", 
                        exception=e, client_ip=client_ip)
        print_server_error("An unexpected error occurred. Please try again later.")

def print_user_error(title, message):
    """Display a user-friendly error page with specific message"""
    print(f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <link rel="stylesheet" href="/static/css/auth.css">
</head>
<body>
    <div class="auth-container">
        <h1>{title}</h1>
        <p class="error">{message}</p>
        <div class="error-actions">
            <a href="/auth/login.html">Go to Login</a> |
            <a href="/auth/register.html">Register</a> |
            <a href="/">Home</a>
        </div>
    </div>
</body>
</html>""")

def print_server_error(message="An unexpected server error occurred."):
    """Display a generic server error page"""
    print(f"""<!DOCTYPE html>
<html>
<head>
    <title>Server Error</title>
    <link rel="stylesheet" href="/static/css/auth.css">
</head>
<body>
    <div class="auth-container">
        <h1>Server Error</h1>
        <p class="error">{message}</p>
        <p>If this problem persists, please contact support.</p>
        <div class="error-actions">
            <a href="/">Return to Home</a>
        </div>
    </div>
</body>
</html>""")

def get_client_context():
    """Extract client context information for logging"""
    return {
        'ip': os.environ.get('REMOTE_ADDR', 'unknown'),
        'user_agent': os.environ.get('HTTP_USER_AGENT', 'unknown'),
        'method': os.environ.get('REQUEST_METHOD', 'unknown'),
        'query': os.environ.get('QUERY_STRING', ''),
        'referer': os.environ.get('HTTP_REFERER', ''),
        'timestamp': datetime.utcnow().isoformat()
    }

def log_form_data(logger, form, client_ip, sensitive_fields=None):
    """Log form data for debugging (excluding sensitive fields)"""
    if sensitive_fields is None:
        sensitive_fields = ['password', 'confirm_password', 'csrf_token']
    
    form_data = {}
    for key in form.keys():
        if key.lower() in [f.lower() for f in sensitive_fields]:
            form_data[key] = '[REDACTED]'
        else:
            form_data[key] = form.getvalue(key, '')
    
    logger.log_info(f"Form data received", client_ip=client_ip, extra={'form_fields': list(form_data.keys())})