#!/usr/bin/env python3
"""User management tool with hot-reload capabilities for PodPlay services."""
import os
import time
import argparse
import subprocess
import shutil
import socket
import crypt
from pathlib import Path
from datetime import datetime

import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def parse_quota(quota_str):
    """Parse quota string (e.g., '100M', '1G') to bytes."""
    if not quota_str:
        return 0

    quota_str = quota_str.upper().strip()
    multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}

    for suffix, multiplier in multipliers.items():
        if quota_str.endswith(suffix):
            try:
                return int(float(quota_str[:-1]) * multiplier)
            except ValueError:
                return 0

    try:
        return int(quota_str)
    except ValueError:
        return 0


def format_quota(bytes_value):
    """Format bytes as human readable quota string."""
    if bytes_value == 0:
        return "0"

    units = [('T', 1024**4), ('G', 1024**3), ('M', 1024**2), ('K', 1024)]
    for unit, divisor in units:
        if bytes_value >= divisor:
            value = bytes_value / divisor
            if value == int(value):
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"

    return str(bytes_value)


class UserConfigEventHandler(FileSystemEventHandler):
    """Handle file system events for user configuration files."""
    
    def __init__(self):
        self.config_extensions = {'.yaml', '.yml', '.json'}
    
    def is_user_config(self, path):
        """Check if a file is a user configuration file."""
        return Path(path).suffix.lower() in self.config_extensions
    
    def on_created(self, event):
        if not event.is_directory and self.is_user_config(event.src_path):
            print(f"[{datetime.now().isoformat()}] New user config: {event.src_path}")
    
    def on_modified(self, event):
        if not event.is_directory and self.is_user_config(event.src_path):
            print(f"[{datetime.now().isoformat()}] Modified user config: {event.src_path}")
    
    def on_deleted(self, event):
        if not event.is_directory and self.is_user_config(event.src_path):
            print(f"[{datetime.now().isoformat()}] Removed user config: {event.src_path}")

class UserReloadStrategy:
    """Base class for user management reload strategies."""
    
    def __init__(self, domain=None):
        self.domain = domain
        self.backup_dir = "/tmp/user-config-backup"
        self.user_data_path = "/data/user-data"
        self.ensure_backup_dir()
    
    def ensure_backup_dir(self):
        """Ensure backup directory exists."""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def log_info(self, message):
        """Log info message with timestamp."""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [INFO] [USER-RELOAD]: {message}")
    
    def log_error(self, message):
        """Log error message with timestamp."""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [ERROR] [USER-RELOAD]: {message}")
    
    def validate_user_config(self, config_path):
        """Validate user configuration format and content."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Basic structure validation
            if not isinstance(config, dict):
                return False
                
            # Check for required fields
            if 'domains' in config:
                for domain in config['domains']:
                    if not all(key in domain for key in ['name', 'users']):
                        return False
                    for user in domain['users']:
                        if not all(key in user for key in ['username', 'password']):
                            return False
            
            return True
        except Exception as e:
            self.log_error(f"User config validation error: {e}")
            return False
    
    def generate_password_hash(self, password, scheme='SHA512-CRYPT'):
        """Generate password hash for Dovecot."""
        try:
            if scheme == 'SHA512-CRYPT':
                return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
            else:
                # Fallback to plain for testing (not recommended for production)
                return password
        except Exception as e:
            self.log_error(f"Password hashing error: {e}")
            return password

class MailUserReloadStrategy(UserReloadStrategy):
    """Mail service user configuration reload implementation."""
    
    def execute(self, config_path):
        """Execute mail service user configuration reload."""
        try:
            # Load and parse user configuration
            if not self.load_user_config(config_path):
                return False
            
            # Create user directories
            if not self.create_user_directories():
                return False
            
            # Generate service configuration files
            if not self.generate_service_configs():
                return False
            
            self.log_info("Reloading Postfix configuration...")
            
            # Rebuild Postfix maps
            subprocess.run(['postmap', '/etc/postfix/vmailbox'], check=True, timeout=30)
            subprocess.run(['postmap', '/etc/postfix/valias'], check=True, timeout=30)
            
            # Reload Postfix
            postfix_result = subprocess.run(['postfix', 'reload'],
                                          capture_output=True, text=True, timeout=30)
            
            if postfix_result.returncode != 0:
                self.log_error(f"Postfix reload failed: {postfix_result.stderr}")
                return False
            
            self.log_info("Reloading Dovecot configuration...")
            
            # Reload Dovecot
            dovecot_result = subprocess.run(['doveadm', 'reload'],
                                          capture_output=True, text=True, timeout=30)
            
            if dovecot_result.returncode != 0:
                self.log_error(f"Dovecot reload failed: {dovecot_result.stderr}")
                return False
            
            self.log_info("Mail service user configuration reload completed")
            return True
                   
        except subprocess.TimeoutExpired:
            self.log_error("Mail service reload timed out")
            return False
        except Exception as e:
            self.log_error(f"Mail user reload error: {e}")
            return False
    
    def load_user_config(self, config_path):
        """Load and parse user configuration."""
        try:
            with open(config_path, 'r') as f:
                self.user_config = yaml.safe_load(f)
            
            self.log_info(f"Loaded user configuration: {config_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to load user config: {e}")
            return False
    
    def create_user_directories(self):
        """Create user directory structure for all users."""
        try:
            self.log_info("Creating user directory structures...")
            
            # Process domain users
            if 'domains' in self.user_config:
                for domain_config in self.user_config['domains']:
                    domain_name = domain_config['name']
                    for user in domain_config['users']:
                        if user.get('enabled', True):
                            username = user['username']
                            if '@' not in username:
                                user_dir = f"{username}@{domain_name}"
                            else:
                                user_dir = username
                            
                            self.create_user_directory(user_dir, user.get('services', ['mail']))
            
            # Process test users
            if 'test_users' in self.user_config:
                for user in self.user_config['test_users']:
                    domain = user['domain']
                    username = user['username']
                    user_dir = f"{username}@{domain}"
                    self.create_user_directory(user_dir, user.get('services', ['mail']))
            
            return True
        except Exception as e:
            self.log_error(f"User directory creation failed: {e}")
            return False
    
    def create_user_directory(self, user_dir, services):
        """Create directory structure for a specific user."""
        user_path = os.path.join(self.user_data_path, 'users', user_dir)
        
        # Create base user directory
        os.makedirs(user_path, exist_ok=True)
        
        # Create service-specific directories
        for service in services:
            if service == 'mail':
                mail_dir = os.path.join(user_path, 'mail', 'Maildir')
                os.makedirs(os.path.join(mail_dir, 'cur'), exist_ok=True)
                os.makedirs(os.path.join(mail_dir, 'new'), exist_ok=True)
                os.makedirs(os.path.join(mail_dir, 'tmp'), exist_ok=True)
                os.makedirs(os.path.join(user_path, 'mail', 'sieve'), exist_ok=True)
            elif service == 'files':
                files_dir = os.path.join(user_path, 'files')
                os.makedirs(os.path.join(files_dir, 'Documents'), exist_ok=True)
                os.makedirs(os.path.join(files_dir, 'Pictures'), exist_ok=True)
                os.makedirs(os.path.join(files_dir, 'Shared'), exist_ok=True)
            elif service == 'git':
                os.makedirs(os.path.join(user_path, 'git'), exist_ok=True)
            elif service == 'www':
                www_dir = os.path.join(user_path, 'www')
                os.makedirs(os.path.join(www_dir, 'public_html'), exist_ok=True)
                os.makedirs(os.path.join(www_dir, 'private'), exist_ok=True)
        
        # Create profile directory
        profile_dir = os.path.join(user_path, '.profile')
        os.makedirs(profile_dir, exist_ok=True)
        
        # Set proper ownership
        try:
            shutil.chown(user_path, user='vmail', group='vmail')
            # Recursively set ownership
            for root, dirs, files in os.walk(user_path):
                for d in dirs:
                    shutil.chown(os.path.join(root, d), user='vmail', group='vmail')
                for f in files:
                    shutil.chown(os.path.join(root, f), user='vmail', group='vmail')
        except Exception as e:
            self.log_error(f"Failed to set ownership for {user_path}: {e}")
    
    def generate_service_configs(self):
        """Generate Postfix and Dovecot configuration files from user definitions."""
        try:
            self.log_info("Generating service configuration files...")
            
            # Generate Postfix virtual mailbox map
            self.generate_vmailbox_map()
            
            # Generate Postfix virtual alias map
            self.generate_valias_map()
            
            # Generate Dovecot password database
            self.generate_dovecot_passwd()
            
            # Configure Dovecot to use passwd-file authentication
            self.configure_dovecot_auth()
            
            self.log_info("Service configuration files generated")
            return True
        except Exception as e:
            self.log_error(f"Configuration generation failed: {e}")
            return False
    
    def generate_vmailbox_map(self):
        """Generate Postfix virtual mailbox map."""
        vmailbox_lines = []
        
        # Process domain users
        if 'domains' in self.user_config:
            for domain_config in self.user_config['domains']:
                domain_name = domain_config['name']
                for user in domain_config['users']:
                    if (user.get('enabled', True) and 
                        'mail' in user.get('services', ['mail'])):
                        username = user['username']
                        if '@' not in username:
                            email = f"{username}@{domain_name}"
                            user_dir = f"{username}@{domain_name}"
                        else:
                            email = username
                            user_dir = username
                        # Use user-data structure: users/{email}/mail/Maildir/
                        vmailbox_lines.append(f"{email} users/{user_dir}/mail/Maildir/")
        
        # Process test users
        if 'test_users' in self.user_config:
            for user in self.user_config['test_users']:
                if 'mail' in user.get('services', ['mail']):
                    domain = user['domain']
                    username = user['username']
                    email = f"{username}@{domain}"
                    user_dir = email
                    vmailbox_lines.append(f"{email} users/{user_dir}/mail/Maildir/")
        
        # Write vmailbox file
        with open('/etc/postfix/vmailbox', 'w') as f:
            f.write('\n'.join(vmailbox_lines) + '\n')
    
    def generate_valias_map(self):
        """Generate Postfix virtual alias map."""
        valias_lines = []
        
        # Process domain users with aliases
        if 'domains' in self.user_config:
            for domain_config in self.user_config['domains']:
                domain_name = domain_config['name']
                for user in domain_config['users']:
                    if (user.get('enabled', True) and 
                        user.get('aliases')):
                        username = user['username']
                        if '@' not in username:
                            target_email = f"{username}@{domain_name}"
                        else:
                            target_email = username
                        
                        for alias in user['aliases']:
                            alias_email = f"{alias}@{domain_name}"
                            valias_lines.append(f"{alias_email} {target_email}")
        
        # Write valias file
        with open('/etc/postfix/valias', 'w') as f:
            f.write('\n'.join(valias_lines) + '\n')
    
    def generate_dovecot_passwd(self):
        """Generate Dovecot password database."""
        passwd_lines = []
        
        # Process domain users
        if 'domains' in self.user_config:
            for domain_config in self.user_config['domains']:
                domain_name = domain_config['name']
                for user in domain_config['users']:
                    if (user.get('enabled', True) and 
                        'mail' in user.get('services', ['mail'])):
                        username = user['username']
                        password = user['password']
                        
                        if '@' not in username:
                            email = f"{username}@{domain_name}"
                            user_dir = f"{username}@{domain_name}"
                        else:
                            email = username
                            user_dir = username
                        
                        # Use existing hash if it's already hashed, otherwise generate new hash
                        if password.startswith("$6$"):
                            password_hash = password  # Already hashed
                        else:
                            password_hash = self.generate_password_hash(password)
                        
                        # Dovecot passwd format: user:password:uid:gid:gecos:home:shell
                        # Use user-data structure for home directory
                        home_dir = f"/data/user-data/users/{user_dir}/mail"
                        passwd_line = f"{email}:{password_hash}:vmail:vmail::{home_dir}::"
                        passwd_lines.append(passwd_line)
        
        # Process test users
        if 'test_users' in self.user_config:
            for user in self.user_config['test_users']:
                if 'mail' in user.get('services', ['mail']):
                    domain = user['domain']
                    username = user['username']
                    password = user['password']
                    email = f"{username}@{domain}"
                    
                    # Use existing hash if it's already hashed, otherwise generate new hash
                    if password.startswith("$6$"):
                        password_hash = password  # Already hashed
                    else:
                        password_hash = self.generate_password_hash(password)
                    home_dir = f"/data/user-data/users/{email}/mail"
                    passwd_line = f"{email}:{password_hash}:vmail:vmail::{home_dir}::"
                    passwd_lines.append(passwd_line)
        
        # Write Dovecot passwd file
        with open('/etc/dovecot/passwd', 'w') as f:
            f.write('\n'.join(passwd_lines) + '\n')
        
        # Set appropriate permissions
        os.chmod('/etc/dovecot/passwd', 0o640)
        try:
            shutil.chown('/etc/dovecot/passwd', group='dovecot')
        except (OSError, KeyError):
            pass  # Ownership changes may fail in containers
    
    def configure_dovecot_auth(self):
        """Configure Dovecot to use passwd-file authentication."""
        try:
            self.log_info("Configuring Dovecot authentication...")
            
            # Update 10-auth.conf to use passwd-file authentication
            auth_conf_path = '/etc/dovecot/conf.d/10-auth.conf'
            
            # Read current configuration
            with open(auth_conf_path, 'r') as f:
                lines = f.readlines()
            
            # Update configuration to use passwd-file instead of system auth
            updated_lines = []
            for line in lines:
                if line.strip() == '!include auth-system.conf.ext':
                    updated_lines.append('#!include auth-system.conf.ext\n')
                    updated_lines.append('!include auth-passwdfile.conf.ext\n')
                elif line.strip() == '#!include auth-passwdfile.conf.ext':
                    updated_lines.append('!include auth-passwdfile.conf.ext\n')
                else:
                    updated_lines.append(line)
            
            # Write updated configuration
            with open(auth_conf_path, 'w') as f:
                f.writelines(updated_lines)
            
            self.log_info("Dovecot authentication configuration updated")
            
        except Exception as e:
            self.log_error(f"Failed to configure Dovecot authentication: {e}")
    
    def authentication_test(self):
        """Test user authentication after reload."""
        try:
            self.log_info("Performing user authentication tests...")
            
            # Test SMTP and IMAP ports are listening
            smtp_ok = self.test_port(25)
            imap_ok = self.test_port(143)
            
            if smtp_ok and imap_ok:
                self.log_info("User authentication tests passed")
                return True
            else:
                self.log_error(f"Authentication tests failed - SMTP: {smtp_ok}, IMAP: {imap_ok}")
                return False
                
        except Exception as e:
            self.log_error(f"Authentication test error: {e}")
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

class HotReloadUserEventHandler(UserConfigEventHandler):
    """Enhanced user configuration event handler with service reload capabilities."""
    
    def __init__(self, service_type, domain=None):
        super().__init__()
        self.service_type = service_type
        self.domain = domain
        self.reload_strategy = self.create_reload_strategy()
        self.debounce_time = 2  # seconds to wait for file operations to complete
        self.pending_reloads = {}  # track pending reloads for debouncing
    
    def create_reload_strategy(self):
        """Create appropriate reload strategy for service type."""
        if self.service_type == 'mail':
            return MailUserReloadStrategy(self.domain)
        else:
            raise ValueError(f"Unknown service type: {self.service_type}")
    
    def on_created(self, event):
        super().on_created(event)
        if not event.is_directory and self.is_user_config(event.src_path):
            self.schedule_reload(event.src_path)
    
    def on_modified(self, event):
        super().on_modified(event)
        if not event.is_directory and self.is_user_config(event.src_path):
            self.schedule_reload(event.src_path)
    
    def schedule_reload(self, config_path):
        """Schedule a reload with debouncing to handle rapid file changes."""
        # Only process users.yaml changes
        if not config_path.endswith('users.yaml'):
            return
            
        # Cancel any pending reload for this path
        if config_path in self.pending_reloads:
            return
        
        self.pending_reloads[config_path] = True
        
        # Schedule reload after debounce period
        def delayed_reload():
            time.sleep(self.debounce_time)
            if config_path in self.pending_reloads:
                del self.pending_reloads[config_path]
                self.handle_user_config_change(config_path)
        
        import threading
        thread = threading.Thread(target=delayed_reload)
        thread.daemon = True
        thread.start()
    
    def handle_user_config_change(self, config_path):
        """Process user configuration change with validation and reload."""
        try:
            self.reload_strategy.log_info(f"Processing user config change: {config_path}")
            
            # 1. Validate new configuration
            if not self.reload_strategy.validate_user_config(config_path):
                self.reload_strategy.log_error(f"Invalid user configuration: {config_path}")
                return
            
            # 2. Backup current configuration
            backup_file = os.path.join(self.reload_strategy.backup_dir, 
                                     f"users-{datetime.now().strftime('%Y%m%d-%H%M%S')}.yaml.backup")
            try:
                shutil.copy2(config_path, backup_file)
                self.reload_strategy.log_info(f"Backed up config: {backup_file}")
            except Exception as e:
                self.reload_strategy.log_error(f"Failed to backup config: {e}")
                # Continue anyway, backup failure shouldn't stop reload
            
            # 3. Trigger service reload
            success = self.reload_strategy.execute(config_path)
            
            # 4. Validate reload success
            if success and self.reload_strategy.authentication_test():
                self.reload_strategy.log_info(f"User configuration hot-reload completed successfully: {config_path}")
            else:
                self.reload_strategy.log_error(f"User configuration reload failed for: {config_path}")
                
        except Exception as e:
            self.reload_strategy.log_error(f"User configuration reload error: {e}")

def watch_user_config_with_reload(path, service_type, domain=None):
    """Watch for changes in user configuration files with hot-reload capability."""
    print(f"Starting user configuration hot-reload monitor for {service_type} service")
    print(f"Watching path: {path}")
    if domain:
        print(f"Domain: {domain}")
    
    # Initial scan
    config_files = list(Path(path).glob('*.yaml')) + list(Path(path).glob('*.yml'))
    if config_files:
        print(f"\nFound {len(config_files)} existing configuration files:")
        for config in config_files:
            print(f"  {config}")
    else:
        print("\nNo configuration files found in the specified path")
    
    # Set up file system observer with hot-reload handler
    event_handler = HotReloadUserEventHandler(service_type, domain)
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
    print(f"\nUser configuration hot-reload monitor active for {service_type}...")
    print("Service will automatically reload when user configuration changes")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nStopping user configuration monitor for {service_type}")
        observer.stop()
    
    observer.join()

def add_user(username, password, domain, quota="100M", services=None, confirm_email=False):
    """Add a new user to the configuration."""
    if services is None:
        services = ["mail"]
    
    config_file = "/data/user-data/config/users.yaml"
    
    try:
        # Load existing configuration
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {"version": "1.0", "domains": [], "test_users": []}
        
        # Add to test_users section for quick testing
        email = f"{username}@{domain}" if '@' not in username else username
        
        # Remove existing user if present
        if 'test_users' not in config:
            config['test_users'] = []
        
        config['test_users'] = [u for u in config['test_users'] 
                               if f"{u['username']}@{u['domain']}" != email]
        
        # Hash password before storing
        strategy = UserReloadStrategy()
        hashed_password = strategy.generate_password_hash(password)
        
        # Add new user
        new_user = {
            "username": username,
            "password": hashed_password,
            "domain": domain,
            "quota": quota,
            "services": services,
            "enabled": True,
            "email_confirmed": confirm_email
        }
        config['test_users'].append(new_user)
        
        # Write updated configuration
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"Added user {email} with quota {quota}")
        return True
        
    except Exception as e:
        print(f"Error adding user: {e}")
        return False

def remove_user(username, domain):
    """Remove a user from the configuration."""
    config_file = "/data/user-data/config/users.yaml"
    
    try:
        if not os.path.exists(config_file):
            print("No user configuration found")
            return False
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        email = f"{username}@{domain}" if '@' not in username else username
        
        # Remove from test_users
        if 'test_users' in config:
            original_count = len(config['test_users'])
            config['test_users'] = [u for u in config['test_users'] 
                                   if f"{u['username']}@{u['domain']}" != email]
            if len(config['test_users']) < original_count:
                print(f"Removed user {email}")
        
        # Remove from domains
        if 'domains' in config:
            for domain_config in config['domains']:
                if domain_config['name'] == domain:
                    original_count = len(domain_config['users'])
                    domain_config['users'] = [u for u in domain_config['users'] 
                                            if u['username'] != username and 
                                               f"{u['username']}@{domain}" != email]
                    if len(domain_config['users']) < original_count:
                        print(f"Removed user {email}")
        
        # Write updated configuration
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return True
        
    except Exception as e:
        print(f"Error removing user: {e}")
        return False

def list_users(domain=None):
    """List all users in the configuration."""
    config_file = "/data/user-data/config/users.yaml"
    
    try:
        if not os.path.exists(config_file):
            print("No user configuration found")
            return
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        print("Users:")
        
        # List test users
        if 'test_users' in config:
            print("\nTest Users:")
            for user in config['test_users']:
                if domain is None or user['domain'] == domain:
                    email = f"{user['username']}@{user['domain']}"
                    quota = user.get('quota', 'N/A')
                    services = ', '.join(user.get('services', ['mail']))
                    print(f"  {email} (quota: {quota}, services: {services})")
        
        # List domain users
        if 'domains' in config:
            for domain_config in config['domains']:
                if domain is None or domain_config['name'] == domain:
                    print(f"\nDomain: {domain_config['name']}")
                    for user in domain_config['users']:
                        username = user['username']
                        email = f"{username}@{domain_config['name']}" if '@' not in username else username
                        quota = user.get('quota', 'N/A')
                        services = ', '.join(user.get('services', ['mail']))
                        enabled = user.get('enabled', True)
                        email_confirmed = user.get('email_confirmed', False)
                        status = []
                        if not enabled:
                            status.append("disabled")
                        else:
                            status.append("enabled")
                        if not email_confirmed:
                            status.append("email unconfirmed")
                        else:
                            status.append("email confirmed")
                        status_str = ", ".join(status)
                        print(f"  {email} (quota: {quota}, services: {services}, {status_str})")
        
    except Exception as e:
        print(f"Error listing users: {e}")

def main():
    parser = argparse.ArgumentParser(description='User management tool with hot-reload capabilities')
    parser.add_argument('--watch', '-w', metavar='PATH',
                        help='Watch path for user configuration changes')
    parser.add_argument('--hot-reload', action='store_true',
                        help='Enable hot-reload functionality for service containers')
    parser.add_argument('--service-type', choices=['mail'],
                        help='Service type for hot-reload (required with --hot-reload)')
    parser.add_argument('--domain', 
                        help='Domain name for user management')
    
    # User management operations
    parser.add_argument('--add-user', action='store_true',
                        help='Add a new user')
    parser.add_argument('--remove-user', action='store_true',
                        help='Remove a user')
    parser.add_argument('--list-users', action='store_true',
                        help='List all users')
    parser.add_argument('--user', help='Username for user operations')
    parser.add_argument('--password', help='Password for user operations')
    parser.add_argument('--quota', default='100M', help='User quota (default: 100M)')
    parser.add_argument('--services', default='mail', 
                        help='Comma-separated list of services (default: mail)')
    parser.add_argument('--confirm-email', action='store_true',
                        help='Mark user email as confirmed (for bootstrap/admin users)')
    
    args = parser.parse_args()
    
    if args.hot_reload and args.watch:
        if not args.service_type:
            parser.error("--service-type is required when using --hot-reload")
        watch_user_config_with_reload(args.watch, args.service_type, args.domain)
    elif args.add_user:
        if not args.user or not args.password or not args.domain:
            parser.error("--user, --password, and --domain are required for --add-user")
        services = [s.strip() for s in args.services.split(',')]
        add_user(args.user, args.password, args.domain, args.quota, services, args.confirm_email)
    elif args.remove_user:
        if not args.user or not args.domain:
            parser.error("--user and --domain are required for --remove-user")
        remove_user(args.user, args.domain)
    elif args.list_users:
        list_users(args.domain)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()