#!/usr/bin/env python3
"""
Test end-to-end email flow: send via SMTP TLS and retrieve via IMAP TLS
"""

import smtplib
import imaplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for colored output
init()

# Configuration
MAIL_SERVER = "localhost"
SMTP_PORT = 2525  # SMTP port with STARTTLS
IMAP_PORT = 2993  # IMAPS port
USERNAME = "admin@lab.sethlakowske.com"
PASSWORD = "password"

def print_success(msg):
    print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

def print_error(msg):
    print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

def print_info(msg):
    print(f"{Fore.BLUE}ℹ {msg}{Style.RESET_ALL}")

def send_test_email():
    """Send a test email via SMTP with TLS"""
    print(f"\n{Fore.YELLOW}=== Sending Test Email ==={Style.RESET_ALL}")
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect to SMTP server
        server = smtplib.SMTP(MAIL_SERVER, SMTP_PORT)
        server.set_debuglevel(0)
        
        # Start TLS
        server.starttls(context=context)
        print_success("TLS connection established")
        
        # Login
        server.login(USERNAME, PASSWORD)
        print_success(f"Authenticated as {USERNAME}")
        
        # Create test email
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = MIMEMultipart()
        msg['From'] = USERNAME
        msg['To'] = USERNAME
        msg['Subject'] = f"Test Email - {timestamp}"
        
        body = f"""Hello!

This is a test email sent via SMTP with TLS encryption at {timestamp}.

The email was sent from {USERNAME} to {USERNAME} using:
- SMTP submission port 587 with STARTTLS
- Let's Encrypt production SSL certificate
- TLS 1.3 encryption

If you can read this message via IMAP, the end-to-end mail flow is working!

Best regards,
Mail Server Test Script
"""
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server.send_message(msg)
        print_success(f"Email sent successfully with subject: 'Test Email - {timestamp}'")
        
        # Quit
        server.quit()
        return timestamp
        
    except Exception as e:
        print_error(f"Failed to send email: {e}")
        return None

def retrieve_test_email(expected_timestamp=None):
    """Retrieve emails via IMAP with TLS"""
    print(f"\n{Fore.YELLOW}=== Retrieving Emails ==={Style.RESET_ALL}")
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect to IMAP server
        server = imaplib.IMAP4_SSL(MAIL_SERVER, IMAP_PORT, ssl_context=context)
        print_success("TLS connection established")
        
        # Login
        server.login(USERNAME, PASSWORD)
        print_success(f"Authenticated as {USERNAME}")
        
        # Select INBOX
        status, data = server.select('INBOX')
        if status != 'OK':
            print_error("Failed to select INBOX")
            return False
            
        message_count = int(data[0].decode())
        print_info(f"INBOX contains {message_count} messages")
        
        if message_count == 0:
            print_info("No messages found in INBOX")
            server.logout()
            return False
        
        # Search for recent messages
        status, message_ids = server.search(None, 'ALL')
        if status != 'OK':
            print_error("Failed to search messages")
            return False
            
        message_list = message_ids[0].split()
        print_info(f"Found {len(message_list)} message(s)")
        
        # Check the most recent message
        if message_list:
            latest_msg_id = message_list[-1]
            
            # Fetch the message
            status, msg_data = server.fetch(latest_msg_id, '(RFC822)')
            if status == 'OK':
                import email
                email_message = email.message_from_bytes(msg_data[0][1])
                
                subject = email_message['Subject']
                from_addr = email_message['From']
                to_addr = email_message['To']
                
                print_success(f"Retrieved email:")
                print_info(f"  Subject: {subject}")
                print_info(f"  From: {from_addr}")
                print_info(f"  To: {to_addr}")
                
                # Check if this is our test email
                if expected_timestamp and expected_timestamp in subject:
                    print_success("✨ Found our test email! End-to-end flow successful!")
                    
                    # Get the body
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                print_info(f"Email body preview: {body[:100]}...")
                                break
                    else:
                        body = email_message.get_payload(decode=True).decode()
                        print_info(f"Email body preview: {body[:100]}...")
                        
                    server.logout()
                    return True
                else:
                    print_info("This is not our test email (different timestamp)")
        
        server.logout()
        return False
        
    except Exception as e:
        print_error(f"Failed to retrieve emails: {e}")
        return False

def main():
    print(f"{Fore.CYAN}=== End-to-End Email Flow Test ==={Style.RESET_ALL}")
    print(f"Testing complete email flow: SMTP TLS → IMAP TLS")
    print(f"Server: {MAIL_SERVER}")
    print(f"User: {USERNAME}")
    
    # Step 1: Send test email
    timestamp = send_test_email()
    if not timestamp:
        print_error("Failed to send test email. Aborting test.")
        return 1
    
    # Step 2: Wait a moment for delivery
    print_info("Waiting 3 seconds for email delivery...")
    time.sleep(3)
    
    # Step 3: Retrieve and verify email
    success = retrieve_test_email(timestamp)
    
    if success:
        print(f"\n{Fore.GREEN}🎉 SUCCESS: End-to-end email flow is working!{Style.RESET_ALL}")
        print_success("✓ Email sent via SMTP with TLS")
        print_success("✓ Email delivered to mailbox")
        print_success("✓ Email retrieved via IMAP with TLS")
        return 0
    else:
        print(f"\n{Fore.RED}❌ FAILED: Could not complete end-to-end flow{Style.RESET_ALL}")
        print_error("Check mail server logs for delivery issues")
        return 1

if __name__ == "__main__":
    exit(main())