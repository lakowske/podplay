#!/usr/bin/env python3
import os
import sys
import time
import argparse
import subprocess
import shutil
import socket
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def find_certificates(path):
    """Find all certificate files (.pem, .crt, .cer) in the given path."""
    cert_extensions = {'.pem', '.crt', '.cer', '.key'}
    certificates = []
    
    path_obj = Path(path)
    if not path_obj.exists():
        print(f"Error: Path '{path}' does not exist", file=sys.stderr)
        return certificates
    
    if path_obj.is_file():
        if path_obj.suffix.lower() in cert_extensions:
            certificates.append(str(path_obj))
    else:
        for file_path in path_obj.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in cert_extensions:
                certificates.append(str(file_path))
    
    return sorted(certificates)

def get_file_info(file_path):
    """Get modification time of a file."""
    try:
        stat = os.stat(file_path)
        return stat.st_mtime
    except OSError:
        return None

class CertificateEventHandler(FileSystemEventHandler):
    """Handle file system events for certificate files."""
    
    def __init__(self):
        self.cert_extensions = {'.pem', '.crt', '.cer', '.key'}
    
    def is_certificate(self, path):
        """Check if a file is a certificate based on its extension."""
        return Path(path).suffix.lower() in self.cert_extensions
    
    def on_created(self, event):
        if not event.is_directory and self.is_certificate(event.src_path):
            print(f"[{datetime.now().isoformat()}] New certificate: {event.src_path}")
    
    def on_modified(self, event):
        if not event.is_directory and self.is_certificate(event.src_path):
            print(f"[{datetime.now().isoformat()}] Modified certificate: {event.src_path}")
    
    def on_deleted(self, event):
        if not event.is_directory and self.is_certificate(event.src_path):
            print(f"[{datetime.now().isoformat()}] Removed certificate: {event.src_path}")
    
    def on_moved(self, event):
        if not event.is_directory:
            if self.is_certificate(event.dest_path):
                print(f"[{datetime.now().isoformat()}] Moved certificate: {event.src_path} -> {event.dest_path}")
            elif self.is_certificate(event.src_path):
                print(f"[{datetime.now().isoformat()}] Removed certificate: {event.src_path}")


class ServiceReloadStrategy:
    """Base class for service-specific reload strategies."""
    
    def __init__(self, domain=None):
        self.domain = domain
        self.backup_dir = "/tmp/cert-backup"
        self.ensure_backup_dir()
    
    def ensure_backup_dir(self):
        """Ensure backup directory exists."""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def log_info(self, message):
        """Log info message with timestamp."""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [INFO] [CERT-RELOAD]: {message}")
    
    def log_error(self, message):
        """Log error message with timestamp."""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [ERROR] [CERT-RELOAD]: {message}")
    
    def validate_certificate(self, cert_path):
        """Validate certificate format and integrity."""
        try:
            # Check if file exists and is readable
            if not os.path.isfile(cert_path):
                return False
            
            # Basic PEM format check
            with open(cert_path, 'r') as f:
                content = f.read()
                if '-----BEGIN CERTIFICATE-----' in content and '-----END CERTIFICATE-----' in content:
                    return True
                elif '-----BEGIN PRIVATE KEY-----' in content and '-----END PRIVATE KEY-----' in content:
                    return True
                elif '-----BEGIN RSA PRIVATE KEY-----' in content and '-----END RSA PRIVATE KEY-----' in content:
                    return True
            
            return False
        except Exception as e:
            self.log_error(f"Certificate validation error: {e}")
            return False
    
    def backup_certificate(self, cert_path):
        """Backup current certificate."""
        try:
            backup_file = os.path.join(self.backup_dir, f"{os.path.basename(cert_path)}.backup")
            if os.path.exists(cert_path):
                shutil.copy2(cert_path, backup_file)
                self.log_info(f"Backed up certificate: {cert_path} -> {backup_file}")
            return True
        except Exception as e:
            self.log_error(f"Certificate backup failed: {e}")
            return False
    
    def execute(self):
        """Execute service reload. Override in subclasses."""
        raise NotImplementedError
    
    def health_check(self):
        """Perform health check after reload. Override in subclasses."""
        raise NotImplementedError


class ApacheReloadStrategy(ServiceReloadStrategy):
    """Apache graceful reload implementation."""
    
    def execute(self):
        """Execute Apache graceful reload."""
        try:
            self.log_info("Testing Apache configuration...")
            
            # Test configuration
            result = subprocess.run(['apache2ctl', 'configtest'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.log_error(f"Apache config test failed: {result.stderr}")
                return False
            
            self.log_info("Apache configuration valid, performing graceful reload...")
            
            # Graceful reload
            result = subprocess.run(['apache2ctl', 'graceful'],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.log_info("Apache graceful reload completed")
                return True
            else:
                self.log_error(f"Apache reload failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_error("Apache reload timed out")
            return False
        except Exception as e:
            self.log_error(f"Apache reload error: {e}")
            return False
    
    def health_check(self):
        """Verify Apache is responding after reload."""
        try:
            self.log_info("Performing Apache health check...")
            
            # Test HTTP endpoint
            http_ok = self.test_port(80)
            https_ok = self.test_port(443)
            
            if http_ok and https_ok:
                self.log_info("Apache health check passed")
                return True
            else:
                self.log_error(f"Apache health check failed - HTTP: {http_ok}, HTTPS: {https_ok}")
                return False
                
        except Exception as e:
            self.log_error(f"Apache health check error: {e}")
            return False
    
    def test_port(self, port):
        """Test if port is listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False


class MailReloadStrategy(ServiceReloadStrategy):
    """Mail service reload implementation."""
    
    def execute(self):
        """Execute mail service reloads."""
        try:
            # Copy certificates to service locations first
            if not self.copy_certificates():
                return False
            
            self.log_info("Reloading Postfix...")
            
            # Reload Postfix
            postfix_result = subprocess.run(['postfix', 'reload'],
                                          capture_output=True, text=True, timeout=30)
            
            if postfix_result.returncode != 0:
                self.log_error(f"Postfix reload failed: {postfix_result.stderr}")
                return False
            
            self.log_info("Reloading Dovecot...")
            
            # Reload Dovecot
            dovecot_result = subprocess.run(['doveadm', 'reload'],
                                          capture_output=True, text=True, timeout=30)
            
            if dovecot_result.returncode != 0:
                self.log_error(f"Dovecot reload failed: {dovecot_result.stderr}")
                return False
            
            self.log_info("Mail services reload completed")
            return True
                   
        except subprocess.TimeoutExpired:
            self.log_error("Mail service reload timed out")
            return False
        except Exception as e:
            self.log_error(f"Mail reload error: {e}")
            return False
    
    def copy_certificates(self):
        """Copy certificates to Postfix and Dovecot locations."""
        try:
            if not self.domain:
                self.log_error("No domain specified for certificate copy")
                return False
            
            cert_file = f"/data/certificates/{self.domain}/fullchain.pem"
            key_file = f"/data/certificates/{self.domain}/privkey.pem"
            
            if not os.path.exists(cert_file) or not os.path.exists(key_file):
                self.log_error(f"Certificate files not found: {cert_file}, {key_file}")
                return False
            
            self.log_info("Copying certificates to mail service locations...")
            
            # Ensure directories exist
            os.makedirs("/etc/ssl/dovecot", exist_ok=True)
            os.makedirs("/etc/ssl/certs/dovecot", exist_ok=True)
            
            # Copy to Dovecot locations
            shutil.copy2(cert_file, "/etc/ssl/dovecot/server.pem")
            shutil.copy2(key_file, "/etc/ssl/dovecot/server.key")
            
            # Copy to Postfix locations  
            shutil.copy2(cert_file, "/etc/ssl/certs/dovecot/fullchain.pem")
            shutil.copy2(key_file, "/etc/ssl/certs/dovecot/privkey.pem")
            
            # Set proper permissions
            self.set_certificate_permissions()
            
            self.log_info("Certificate copy completed")
            return True
            
        except Exception as e:
            self.log_error(f"Certificate copy failed: {e}")
            return False
    
    def set_certificate_permissions(self):
        """Set proper permissions for copied certificates."""
        try:
            # Set Dovecot permissions
            os.chmod("/etc/ssl/dovecot/server.pem", 0o644)
            os.chmod("/etc/ssl/dovecot/server.key", 0o640)
            
            # Set Postfix permissions
            os.chmod("/etc/ssl/certs/dovecot/fullchain.pem", 0o644)
            os.chmod("/etc/ssl/certs/dovecot/privkey.pem", 0o640)
            
            # Change ownership (may fail in containers, but that's OK)
            try:
                shutil.chown("/etc/ssl/dovecot/server.key", group="dovecot")
                shutil.chown("/etc/ssl/certs/dovecot/privkey.pem", group="postfix")
            except:
                pass  # Ownership changes may fail in containers
                
        except Exception as e:
            self.log_error(f"Permission setting failed: {e}")
    
    def health_check(self):
        """Verify mail services are responding after reload."""
        try:
            self.log_info("Performing mail service health check...")
            
            # Test SMTP ports
            smtp_ok = self.test_port(25)
            submission_ok = self.test_port(587)
            
            # Test IMAP ports  
            imap_ok = self.test_port(143)
            imaps_ok = self.test_port(993)
            
            if smtp_ok and imap_ok:
                self.log_info("Mail service health check passed")
                return True
            else:
                self.log_error(f"Mail health check failed - SMTP: {smtp_ok}, IMAP: {imap_ok}")
                return False
                
        except Exception as e:
            self.log_error(f"Mail health check error: {e}")
            return False
    
    def test_port(self, port):
        """Test if port is listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False


class HotReloadEventHandler(CertificateEventHandler):
    """Enhanced certificate event handler with service reload capabilities."""
    
    def __init__(self, service_type, domain=None):
        super().__init__()
        self.service_type = service_type
        self.domain = domain
        self.reload_strategy = self.create_reload_strategy()
        self.debounce_time = 2  # seconds to wait for file operations to complete
        self.pending_reloads = {}  # track pending reloads for debouncing
    
    def create_reload_strategy(self):
        """Create appropriate reload strategy for service type."""
        if self.service_type == 'apache':
            return ApacheReloadStrategy(self.domain)
        elif self.service_type == 'mail':
            return MailReloadStrategy(self.domain)
        else:
            raise ValueError(f"Unknown service type: {self.service_type}")
    
    def on_created(self, event):
        super().on_created(event)
        if not event.is_directory and self.is_certificate(event.src_path):
            self.schedule_reload(event.src_path)
    
    def on_modified(self, event):
        super().on_modified(event)
        if not event.is_directory and self.is_certificate(event.src_path):
            self.schedule_reload(event.src_path)
    
    def schedule_reload(self, cert_path):
        """Schedule a reload with debouncing to handle rapid file changes."""
        # Cancel any pending reload for this path
        if cert_path in self.pending_reloads:
            return
        
        self.pending_reloads[cert_path] = True
        
        # Schedule reload after debounce period
        def delayed_reload():
            time.sleep(self.debounce_time)
            if cert_path in self.pending_reloads:
                del self.pending_reloads[cert_path]
                self.handle_certificate_change(cert_path)
        
        import threading
        thread = threading.Thread(target=delayed_reload)
        thread.daemon = True
        thread.start()
    
    def handle_certificate_change(self, cert_path):
        """Process certificate change with validation and reload."""
        try:
            self.reload_strategy.log_info(f"Processing certificate change: {cert_path}")
            
            # 1. Validate new certificate
            if not self.reload_strategy.validate_certificate(cert_path):
                self.reload_strategy.log_error(f"Invalid certificate: {cert_path}")
                return
            
            # 2. Backup current certificate
            if not self.reload_strategy.backup_certificate(cert_path):
                self.reload_strategy.log_error(f"Failed to backup certificate: {cert_path}")
                # Continue anyway, backup failure shouldn't stop reload
            
            # 3. Trigger service reload
            success = self.reload_strategy.execute()
            
            # 4. Validate reload success
            if success and self.reload_strategy.health_check():
                self.reload_strategy.log_info(f"Certificate hot-reload completed successfully: {cert_path}")
            else:
                self.reload_strategy.log_error(f"Certificate reload failed for: {cert_path}")
                # Note: In a more sophisticated implementation, we might attempt rollback here
                
        except Exception as e:
            self.reload_strategy.log_error(f"Certificate reload error: {e}")


def watch_certificates_with_reload(path, service_type, domain=None):
    """Watch for changes in certificate files with hot-reload capability."""
    print(f"Starting certificate hot-reload monitor for {service_type} service")
    print(f"Watching path: {path}")
    if domain:
        print(f"Domain: {domain}")
    
    # Initial scan
    certificates = find_certificates(path)
    if certificates:
        print(f"\nFound {len(certificates)} existing certificates:")
        for cert in certificates:
            print(f"  {cert}")
    else:
        print("\nNo certificates found in the specified path")
    
    # Set up file system observer with hot-reload handler
    event_handler = HotReloadEventHandler(service_type, domain)
    observer = Observer()
    
    path_obj = Path(path)
    if path_obj.is_file():
        # Watch the directory containing the file
        observer.schedule(event_handler, str(path_obj.parent), recursive=False)
    else:
        # Watch the directory recursively
        observer.schedule(event_handler, str(path_obj), recursive=True)
    
    # Start watching
    observer.start()
    print(f"\nCertificate hot-reload monitor active for {service_type}...")
    print("Service will automatically reload when certificates change")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nStopping certificate monitor for {service_type}")
        observer.stop()
    
    observer.join()


def watch_certificates(path, interval=None):
    """Watch for changes in certificate files using file system events."""
    print(f"Watching for certificate changes in: {path}")
    print("Using file system event monitoring (no polling)")
    
    # Initial scan
    certificates = find_certificates(path)
    if certificates:
        print("\nFound existing certificates:")
        for cert in certificates:
            print(f"  {cert}")
    else:
        print("\nNo certificates found in the specified path")
    
    # Set up file system observer
    event_handler = CertificateEventHandler()
    observer = Observer()
    
    path_obj = Path(path)
    if path_obj.is_file():
        # Watch the directory containing the file
        observer.schedule(event_handler, str(path_obj.parent), recursive=False)
    else:
        # Watch the directory recursively
        observer.schedule(event_handler, str(path_obj), recursive=True)
    
    # Start watching
    observer.start()
    print("\nWatching for changes... (Press Ctrl+C to stop)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping certificate watch")
        observer.stop()
    
    observer.join()

def main():
    parser = argparse.ArgumentParser(description='Certificate management tool with hot-reload capabilities')
    parser.add_argument('path', help='Path to search for certificates')
    parser.add_argument('--watch', '-w', action='store_true', 
                        help='Watch for changes in certificates (uses file system events)')
    parser.add_argument('--hot-reload', action='store_true',
                        help='Enable hot-reload functionality for service containers')
    parser.add_argument('--service-type', choices=['apache', 'mail'],
                        help='Service type for hot-reload (required with --hot-reload)')
    parser.add_argument('--domain', 
                        help='Domain name for certificate management')
    
    args = parser.parse_args()
    
    if args.hot_reload:
        if not args.service_type:
            parser.error("--service-type is required when using --hot-reload")
        watch_certificates_with_reload(args.path, args.service_type, args.domain)
    elif args.watch:
        watch_certificates(args.path)
    else:
        certificates = find_certificates(args.path)
        if certificates:
            print("Found certificates:")
            for cert in certificates:
                print(f"  {cert}")
        else:
            print("No certificates found")

if __name__ == '__main__':
    main()