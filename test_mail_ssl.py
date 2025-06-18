#!/usr/bin/env python3
"""
Test script for mail server SSL/TLS functionality
Tests both SMTP and IMAP with SSL/TLS connections
"""

import smtplib
import imaplib
import ssl
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from colorama import init, Fore, Style
import socket

# Initialize colorama for colored output
init()

# Configuration
MAIL_SERVER = "localhost"
SMTP_PORT = 9587  # TLS required port
SMTP_STARTTLS_PORT = 9025  # STARTTLS port
IMAP_PORT = 9993  # IMAPS port
IMAP_STARTTLS_PORT = 9143  # IMAP with STARTTLS
USERNAME = "admin@lab.sethlakowske.com"
PASSWORD = "password"

def print_success(msg):
    print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

def print_error(msg):
    print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

def print_info(msg):
    print(f"{Fore.BLUE}ℹ {msg}{Style.RESET_ALL}")

def test_smtp_tls():
    """Test SMTP with TLS (port 587)"""
    print(f"\n{Fore.YELLOW}Testing SMTP with TLS on port {SMTP_PORT}...{Style.RESET_ALL}")
    
    try:
        # Create SSL context that accepts self-signed certificates
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect to SMTP server
        server = smtplib.SMTP(MAIL_SERVER, SMTP_PORT)
        server.set_debuglevel(0)  # Set to 1 for verbose output
        
        # Start TLS
        server.starttls(context=context)
        print_success("STARTTLS initiated successfully")
        
        # Get cipher info
        cipher = server.sock.cipher()
        if cipher:
            print_info(f"Cipher suite: {cipher[0]}")
            print_info(f"Protocol: {cipher[1]}")
            print_info(f"Cipher bits: {cipher[2]}")
        
        # Login
        server.login(USERNAME, PASSWORD)
        print_success(f"Authentication successful for {USERNAME}")
        
        # Send test email
        msg = MIMEMultipart()
        msg['From'] = USERNAME
        msg['To'] = USERNAME
        msg['Subject'] = f"SSL/TLS Test - {datetime.now()}"
        
        body = "This is a test email sent via SMTP with TLS encryption."
        msg.attach(MIMEText(body, 'plain'))
        
        server.send_message(msg)
        print_success("Test email sent successfully")
        
        # Quit
        server.quit()
        print_success("SMTP TLS test completed successfully")
        return True
        
    except Exception as e:
        print_error(f"SMTP TLS test failed: {e}")
        return False

def test_smtp_starttls():
    """Test SMTP with STARTTLS (port 25)"""
    print(f"\n{Fore.YELLOW}Testing SMTP with STARTTLS on port {SMTP_STARTTLS_PORT}...{Style.RESET_ALL}")
    
    try:
        # Create SSL context that accepts self-signed certificates
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect to SMTP server
        server = smtplib.SMTP(MAIL_SERVER, SMTP_STARTTLS_PORT)
        server.set_debuglevel(0)
        
        # Check if STARTTLS is supported
        server.ehlo()
        if server.has_extn('STARTTLS'):
            print_success("STARTTLS is supported")
            
            # Start TLS
            server.starttls(context=context)
            print_success("STARTTLS initiated successfully")
            
            # Re-identify after STARTTLS
            server.ehlo()
            
            # Login
            server.login(USERNAME, PASSWORD)
            print_success(f"Authentication successful for {USERNAME}")
            
            server.quit()
            print_success("SMTP STARTTLS test completed successfully")
            return True
        else:
            print_error("STARTTLS not supported")
            return False
            
    except Exception as e:
        print_error(f"SMTP STARTTLS test failed: {e}")
        return False

def test_imap_ssl():
    """Test IMAP with SSL/TLS (port 993)"""
    print(f"\n{Fore.YELLOW}Testing IMAP with SSL/TLS on port {IMAP_PORT}...{Style.RESET_ALL}")
    
    try:
        # Create SSL context that accepts self-signed certificates
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect to IMAP server
        server = imaplib.IMAP4_SSL(MAIL_SERVER, IMAP_PORT, ssl_context=context)
        print_success("SSL/TLS connection established")
        
        # Get SSL info
        ssl_info = server.socket().cipher()
        if ssl_info:
            print_info(f"Cipher suite: {ssl_info[0]}")
            print_info(f"Protocol: {ssl_info[1]}")
        
        # Login
        server.login(USERNAME, PASSWORD)
        print_success(f"Authentication successful for {USERNAME}")
        
        # List mailboxes
        status, mailboxes = server.list()
        if status == 'OK':
            print_info(f"Mailboxes: {len(mailboxes)}")
            
        # Select INBOX
        status, data = server.select('INBOX')
        if status == 'OK':
            print_success(f"INBOX selected, contains {data[0].decode()} messages")
            
        # Logout
        server.logout()
        print_success("IMAP SSL/TLS test completed successfully")
        return True
        
    except Exception as e:
        print_error(f"IMAP SSL/TLS test failed: {e}")
        return False

def test_imap_starttls():
    """Test IMAP with STARTTLS (port 143)"""
    print(f"\n{Fore.YELLOW}Testing IMAP with STARTTLS on port {IMAP_STARTTLS_PORT}...{Style.RESET_ALL}")
    
    try:
        # Connect to IMAP server
        server = imaplib.IMAP4(MAIL_SERVER, IMAP_STARTTLS_PORT)
        print_success("Plain connection established")
        
        # Start TLS
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        server.starttls(ssl_context=context)
        print_success("STARTTLS initiated successfully")
        
        # Login
        server.login(USERNAME, PASSWORD)
        print_success(f"Authentication successful for {USERNAME}")
        
        # Logout
        server.logout()
        print_success("IMAP STARTTLS test completed successfully")
        return True
        
    except Exception as e:
        print_error(f"IMAP STARTTLS test failed: {e}")
        return False

def check_port_open(host, port):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def main():
    print(f"{Fore.CYAN}=== Mail Server SSL/TLS Test ==={Style.RESET_ALL}")
    print(f"Server: {MAIL_SERVER}")
    print(f"User: {USERNAME}")
    print(f"Testing SSL/TLS functionality...\n")
    
    # Check ports
    print(f"{Fore.YELLOW}Checking port availability...{Style.RESET_ALL}")
    ports = [
        (SMTP_STARTTLS_PORT, "SMTP STARTTLS"),
        (SMTP_PORT, "SMTP TLS"),
        (IMAP_STARTTLS_PORT, "IMAP STARTTLS"),
        (IMAP_PORT, "IMAP SSL/TLS")
    ]
    
    all_ports_open = True
    for port, service in ports:
        if check_port_open(MAIL_SERVER, port):
            print_success(f"Port {port} ({service}) is open")
        else:
            print_error(f"Port {port} ({service}) is closed")
            all_ports_open = False
    
    if not all_ports_open:
        print_error("\nSome ports are not accessible. Make sure the mail container is running.")
        sys.exit(1)
    
    # Run tests
    results = []
    results.append(("SMTP STARTTLS", test_smtp_starttls()))
    results.append(("SMTP TLS", test_smtp_tls()))
    results.append(("IMAP SSL/TLS", test_imap_ssl()))
    results.append(("IMAP STARTTLS", test_imap_starttls()))
    
    # Summary
    print(f"\n{Fore.CYAN}=== Test Summary ==={Style.RESET_ALL}")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\n{Fore.CYAN}Total: {passed}/{total} tests passed{Style.RESET_ALL}")
    
    if passed == total:
        print_success("\nAll SSL/TLS tests passed!")
        return 0
    else:
        print_error(f"\n{total - passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())