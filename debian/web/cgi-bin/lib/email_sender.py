import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class PlainSMTP(smtplib.SMTP):
    """SMTP client that never uses STARTTLS"""
    def starttls(self, *args, **kwargs):
        # Override to prevent automatic STARTTLS
        # Intentionally ignore all arguments
        _ = args, kwargs
        pass

class EmailSender:
    def __init__(self):
        self.smtp_host = "localhost"
        self.smtp_port = 25  # Use standard SMTP port
        self.smtp_user = None  # Try without authentication first
        self.smtp_password = None
        self.from_addr = "PodPlay System <noreply@lab.sethlakowske.com>"
        self.template_dir = Path("/var/www/templates/emails")
    
    def send_confirmation_email(self, to_email, username, confirmation_url):
        """Send registration confirmation email"""
        try:
            # Load template
            text_template_path = self.template_dir / "confirmation.txt"
            html_template_path = self.template_dir / "confirmation.html"
            
            if text_template_path.exists():
                with open(text_template_path, "r") as f:
                    text_template = f.read()
            else:
                # Default template if file doesn't exist
                text_template = """Hello {username},

Welcome to PodPlay! Please confirm your email address by clicking the link below:

{confirmation_url}

This link will expire in 1 hour.

If you did not create an account, please ignore this email.

Best regards,
The PodPlay Team
{domain}"""
            
            if html_template_path.exists():
                with open(html_template_path, "r") as f:
                    html_template = f.read()
            else:
                # Default HTML template
                html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #007bff;">Welcome to PodPlay!</h1>
        <p>Hello {username},</p>
        <p>Thank you for registering with PodPlay. To complete your registration, 
        please confirm your email address by clicking the button below:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{confirmation_url}" style="display: inline-block; padding: 12px 30px; 
            background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">
            Confirm Email Address</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 3px;">
            {confirmation_url}
        </p>
        <p><strong>This link will expire in 1 hour.</strong></p>
        <p>If you did not create an account, please ignore this email.</p>
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="text-align: center; color: #666; font-size: 0.9em;">
            Best regards,<br>The PodPlay Team<br>{domain}
        </p>
    </div>
</body>
</html>"""
            
            # Replace placeholders
            replacements = {
                '{username}': username,
                '{confirmation_url}': confirmation_url,
                '{domain}': 'lab.sethlakowske.com'
            }
            
            text_content = text_template
            html_content = html_template
            
            for key, value in replacements.items():
                text_content = text_content.replace(key, value)
                html_content = html_content.replace(key, value)
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = 'Confirm your PodPlay account'
            message['From'] = self.from_addr
            message['To'] = to_email
            
            # Add parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email using plain SMTP (no encryption for local server)
            with PlainSMTP(self.smtp_host, self.smtp_port) as server:
                # Explicitly avoid STARTTLS for local mail server
                # (smtplib automatically tries STARTTLS if available, we need plain SMTP)
                if self.smtp_user and self.smtp_password:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send confirmation email to {to_email}: {e}")
            return False
    
    def send_reset_email(self, to_email, username, reset_url):
        """Send password reset email"""
        try:
            # Load template
            text_template_path = self.template_dir / "reset.txt"
            html_template_path = self.template_dir / "reset.html"
            
            if text_template_path.exists():
                with open(text_template_path, "r") as f:
                    text_template = f.read()
            else:
                # Default template
                text_template = """Hello {username},

We received a request to reset your PodPlay password. Click the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email. Your password will not be changed.

Best regards,
The PodPlay Team
{domain}"""
            
            if html_template_path.exists():
                with open(html_template_path, "r") as f:
                    html_template = f.read()
            else:
                # Default HTML template
                html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #007bff;">Password Reset Request</h1>
        <p>Hello {username},</p>
        <p>We received a request to reset your PodPlay password. Click the button below to set a new password:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="display: inline-block; padding: 12px 30px; 
            background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">
            Reset Password</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; background: #e9ecef; padding: 10px; border-radius: 3px;">
            {reset_url}
        </p>
        <p><strong>This link will expire in 1 hour.</strong></p>
        <p>If you did not request a password reset, please ignore this email. Your password will not be changed.</p>
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        <p style="text-align: center; color: #666; font-size: 0.9em;">
            Best regards,<br>The PodPlay Team<br>{domain}
        </p>
    </div>
</body>
</html>"""
            
            # Replace placeholders
            replacements = {
                '{username}': username,
                '{reset_url}': reset_url,
                '{domain}': 'lab.sethlakowske.com'
            }
            
            text_content = text_template
            html_content = html_template
            
            for key, value in replacements.items():
                text_content = text_content.replace(key, value)
                html_content = html_content.replace(key, value)
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = 'Reset your PodPlay password'
            message['From'] = self.from_addr
            message['To'] = to_email
            
            # Add parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email using plain SMTP (no encryption for local server)
            with PlainSMTP(self.smtp_host, self.smtp_port) as server:
                # Explicitly avoid STARTTLS for local mail server
                # (smtplib automatically tries STARTTLS if available, we need plain SMTP)
                if self.smtp_user and self.smtp_password:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send reset email to {to_email}: {e}")
            return False