#!/data/.venv/bin/python3
"""
Send Email CGI Script for Admin Operations
"""

import cgi
import os
import sys
import json
from pathlib import Path

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from session import SessionManager
from csrf import CSRFProtection
from user_db import UserDatabase
from cgi_wrapper import get_client_context, log_form_data
from logger import CGILogger, ValidationError, AuthenticationError

# Add email sender from web cgi-bin
sys.path.insert(0, '/var/www/cgi-bin/lib')
from email_sender import EmailSender

def is_admin(session_id):
    """Check if the current session belongs to an admin user."""
    if not session_id:
        return False
    
    session_mgr = SessionManager()
    session = session_mgr.get_session(session_id)
    if not session:
        return False
    
    # Check if user is admin
    user_email = session.get('user_email', '')
    # Simple check - in production, check against role database
    return user_email.startswith('admin@')

def send_custom_email(to_email, subject, message, from_name=None):
    """Send a custom email to a user."""
    try:
        # Validate recipient exists
        user_db = UserDatabase()
        if not user_db.user_exists(to_email):
            return False, "User not found"
        
        # Get user info for personalization
        user_info = user_db.get_user_info(to_email)
        username = user_info['username'] if user_info else to_email.split('@')[0]
        
        # Prepare email content
        email_sender = EmailSender()
        
        # Override from address if from_name provided
        if from_name:
            email_sender.from_addr = f"{from_name} <noreply@lab.sethlakowske.com>"
        
        # Create message templates
        text_template = """Hello {username},

{message}

Best regards,
{from_name}
PodPlay System"""
        
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #007bff;">{subject}</h1>
        <p>Hello {username},</p>
        <div style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #007bff;">
            {message_html}
        </div>
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="text-align: center; color: #666; font-size: 0.9em;">
            Best regards,<br>{from_name}<br>PodPlay System
        </p>
    </div>
</body>
</html>"""
        
        # Replace placeholders
        from_display = from_name or "PodPlay Admin"
        message_html = message.replace('\n', '<br>')
        
        replacements = {
            '{username}': username,
            '{message}': message,
            '{message_html}': message_html,
            '{subject}': subject,
            '{from_name}': from_display
        }
        
        text_content = text_template
        html_content = html_template
        
        for key, value in replacements.items():
            text_content = text_content.replace(key, value)
            html_content = html_content.replace(key, value)
        
        # Send using existing infrastructure
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        message_obj = MIMEMultipart('alternative')
        message_obj['Subject'] = subject
        message_obj['From'] = email_sender.from_addr
        message_obj['To'] = to_email
        
        # Add parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        message_obj.attach(text_part)
        message_obj.attach(html_part)
        
        # Send email using EmailSender's SMTP connection
        from email_sender import PlainSMTP
        with PlainSMTP(email_sender.smtp_host, email_sender.smtp_port) as server:
            if email_sender.smtp_user and email_sender.smtp_password:
                import ssl
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.login(email_sender.smtp_user, email_sender.smtp_password)
            server.send_message(message_obj)
        
        return True, "Email sent successfully"
        
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

def email_main():
    """Main email sending logic."""
    
    # Initialize logger and get client context
    logger = CGILogger("send-email.py")
    client_context = get_client_context()
    client_ip = client_context['ip']
    
    # Parse form data
    form = cgi.FieldStorage()
    log_form_data(logger, form, client_ip)
    
    # Get session ID from cookies
    session_id = None
    cookie_header = os.environ.get('HTTP_COOKIE', '')
    for cookie in cookie_header.split(';'):
        if '=' in cookie:
            name, value = cookie.strip().split('=', 1)
            if name == 'session_id':
                session_id = value
                break
    
    # Check admin authorization
    if not is_admin(session_id):
        logger.log_security_event("unauthorized_email_attempt", 
                                "Non-admin tried to send email", client_ip=client_ip)
        print("Status: 403 Forbidden")
        print("Content-Type: application/json")
        print()
        print(json.dumps({"error": "Admin privileges required"}))
        return
    
    # Validate CSRF token for non-GET requests
    if os.environ.get('REQUEST_METHOD') == 'POST':
        csrf = CSRFProtection()
        csrf_token = form.getvalue('csrf_token', '')
        if not csrf.validate_token(csrf_token):
            logger.log_security_event("csrf_failure", "Invalid CSRF token for email send", 
                                    client_ip=client_ip)
            print("Status: 403 Forbidden")
            print("Content-Type: application/json")
            print()
            print(json.dumps({"error": "Invalid CSRF token"}))
            return
    
    # Get parameters
    to_email = form.getvalue('to_email', '').strip()
    subject = form.getvalue('subject', '').strip()
    message = form.getvalue('message', '').strip()
    from_name = form.getvalue('from_name', '').strip()
    
    # Validate required fields
    if not to_email:
        print("Status: 400 Bad Request")
        print("Content-Type: application/json")
        print()
        print(json.dumps({"error": "Recipient email is required"}))
        return
    
    if not subject:
        print("Status: 400 Bad Request")
        print("Content-Type: application/json")
        print()
        print(json.dumps({"error": "Subject is required"}))
        return
    
    if not message:
        print("Status: 400 Bad Request")
        print("Content-Type: application/json")
        print()
        print(json.dumps({"error": "Message is required"}))
        return
    
    # Send email
    success, result_message = send_custom_email(to_email, subject, message, from_name)
    
    # Log the attempt
    logger.log_info(f"Email send attempt - To: {to_email}, Subject: {subject}, Success: {success}",
                   client_ip=client_ip, extra={'recipient': to_email, 'subject': subject})
    
    # Return response
    print("Content-Type: application/json")
    print()
    
    if success:
        print(json.dumps({
            "success": True,
            "message": result_message,
            "recipient": to_email,
            "subject": subject
        }))
    else:
        print(json.dumps({
            "success": False,
            "error": result_message
        }))

if __name__ == "__main__":
    # Don't use cgi_main_wrapper to control headers properly
    try:
        email_main()
    except Exception as e:
        print("Status: 500 Internal Server Error")
        print("Content-Type: application/json")
        print()
        print(json.dumps({"error": "Internal server error"}))