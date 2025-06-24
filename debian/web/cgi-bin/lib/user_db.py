import yaml
import crypt
import hashlib
from pathlib import Path

class UserDatabase:
    def __init__(self):
        self.users_config = Path("/data/user-data/config/users.yaml")
        self.dovecot_passwd = Path("/etc/dovecot/passwd")
    
    def authenticate(self, email, password):
        """Authenticate user against users.yaml configuration"""
        if not self.users_config.exists():
            return False
        
        try:
            with open(self.users_config, "r") as f:
                config = yaml.safe_load(f)
            
            # Check domain users first
            if 'domains' in config:
                for domain_config in config['domains']:
                    for user in domain_config.get('users', []):
                        user_email = None
                        if '@' in user.get('username', ''):
                            user_email = user['username']
                        else:
                            user_email = f"{user['username']}@{domain_config['name']}"
                        
                        if user_email == email:
                            # Check if user is enabled
                            if not user.get('enabled', True):
                                return False
                            
                            # Check email confirmation (if required)
                            if not user.get('email_confirmed', False):
                                return False
                            
                            stored_hash = user.get('password', '')
                            return self.verify_password(password, stored_hash)
            
            # Check test users (for admin and testing)
            if 'test_users' in config:
                for user in config['test_users']:
                    # Construct email from username and domain
                    user_email = f"{user['username']}@{user['domain']}"
                    
                    if user_email == email:
                        # Check if user is enabled
                        if not user.get('enabled', True):
                            return False
                        
                        # Check email confirmation (if required)
                        if not user.get('email_confirmed', False):
                            return False
                        
                        stored_hash = user.get('password', '')
                        return self.verify_password(password, stored_hash)
            
        except Exception:
            return False
        
        return False
    
    def verify_password(self, password, stored_hash):
        """Verify password against hash"""
        if stored_hash.startswith("$6$"):  # SHA512-CRYPT
            return crypt.crypt(password, stored_hash) == stored_hash
        else:
            # Plain text (for development only)
            return password == stored_hash
    
    def hash_password(self, password):
        """Hash password using SHA512-CRYPT"""
        return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    
    def user_exists(self, email):
        """Check if user exists"""
        if not self.users_config.exists():
            return False
        
        try:
            with open(self.users_config, "r") as f:
                config = yaml.safe_load(f)
            
            # Check domain users
            if 'domains' in config:
                for domain_config in config['domains']:
                    for user in domain_config.get('users', []):
                        if '@' in user.get('username', ''):
                            if user['username'] == email:
                                return True
                        else:
                            user_email = f"{user['username']}@{domain_config['name']}"
                            if user_email == email:
                                return True
            
            # Check test users
            if 'test_users' in config:
                for user in config['test_users']:
                    user_email = f"{user['username']}@{user['domain']}"
                    if user_email == email:
                        return True
        except Exception:
            return False
        
        return False
    
    def add_user(self, user_data):
        """Add user to configuration"""
        # Load existing config
        if self.users_config.exists():
            with open(self.users_config, "r") as f:
                config = yaml.safe_load(f)
        else:
            config = {'version': '1.0', 'domains': []}
        
        # Ensure config has proper structure
        if not config:
            config = {'version': '1.0', 'domains': []}
        if 'domains' not in config:
            config['domains'] = []
        
        # Find or create domain entry
        domain = user_data['domain']
        domain_config = None
        
        for dc in config.get('domains', []):
            if dc['name'] == domain:
                domain_config = dc
                break
        
        if not domain_config:
            domain_config = {'name': domain, 'users': []}
            config['domains'].append(domain_config)
        
        # Ensure users list exists
        if 'users' not in domain_config:
            domain_config['users'] = []
        
        # Add user
        username = user_data['email'].split('@')[0]
        new_user = {
            'username': username,
            'password': user_data.get('password', ''),  # Already hashed
            'aliases': [],
            'quota': user_data.get('quota', '500M'),
            'enabled': user_data.get('enabled', True),  # Allow setting enabled state
            'email_confirmed': user_data.get('email_confirmed', False),  # Email confirmation status
            'services': user_data.get('services', ['mail'])
        }
        
        domain_config['users'].append(new_user)
        
        # Save config
        with open(self.users_config, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        
        # Touch file to trigger hot reload
        self.users_config.touch()
    
    def update_password(self, email, new_password_hash):
        """Update user password"""
        if not self.users_config.exists():
            return False
        
        try:
            with open(self.users_config, "r") as f:
                config = yaml.safe_load(f)
            
            updated = False
            
            if 'domains' in config:
                for domain_config in config['domains']:
                    for user in domain_config.get('users', []):
                        user_email = None
                        if '@' in user.get('username', ''):
                            user_email = user['username']
                        else:
                            user_email = f"{user['username']}@{domain_config['name']}"
                        
                        if user_email == email:
                            user['password'] = new_password_hash
                            updated = True
                            break
                    
                    if updated:
                        break
            
            if updated:
                # Save config
                with open(self.users_config, "w") as f:
                    yaml.dump(config, f, default_flow_style=False)
                
                # Touch file to trigger hot reload
                self.users_config.touch()
                return True
                
        except Exception:
            return False
        
        return False
    
    def get_user_info(self, email):
        """Get user information"""
        if not self.users_config.exists():
            return None
        
        try:
            with open(self.users_config, "r") as f:
                config = yaml.safe_load(f)
            
            # Check domain users
            if 'domains' in config:
                for domain_config in config['domains']:
                    for user in domain_config.get('users', []):
                        user_email = None
                        if '@' in user.get('username', ''):
                            user_email = user['username']
                        else:
                            user_email = f"{user['username']}@{domain_config['name']}"
                        
                        if user_email == email:
                            return {
                                'email': user_email,
                                'username': user['username'],
                                'domain': domain_config['name'],
                                'quota': user.get('quota', '500M'),
                                'services': user.get('services', ['mail']),
                                'enabled': user.get('enabled', True)
                            }
            
            # Check test users
            if 'test_users' in config:
                for user in config['test_users']:
                    user_email = f"{user['username']}@{user['domain']}"
                    
                    if user_email == email:
                        return {
                            'email': user_email,
                            'username': user['username'],
                            'domain': user['domain'],
                            'quota': user.get('quota', '500M'),
                            'services': user.get('services', ['mail']),
                            'enabled': user.get('enabled', True)
                        }
        except Exception:
            return None
        
        return None
    
    def enable_user(self, email):
        """Enable a user account"""
        if not self.users_config.exists():
            return False
        
        try:
            with open(self.users_config, "r") as f:
                config = yaml.safe_load(f)
            
            updated = False
            
            if 'domains' in config:
                for domain_config in config['domains']:
                    for user in domain_config.get('users', []):
                        user_email = None
                        if '@' in user.get('username', ''):
                            user_email = user['username']
                        else:
                            user_email = f"{user['username']}@{domain_config['name']}"
                        
                        if user_email == email:
                            user['email_confirmed'] = True
                            updated = True
                            break
                    
                    if updated:
                        break
            
            if updated:
                # Save config
                with open(self.users_config, "w") as f:
                    yaml.dump(config, f, default_flow_style=False)
                
                # Touch file to trigger hot reload
                self.users_config.touch()
                return True
                
        except Exception:
            return False
        
        return False