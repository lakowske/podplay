import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

class RateLimiter:
    def __init__(self):
        self.storage_dir = Path("/data/user-data/pending/rate_limits")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Define rate limits
        self.limits = {
            'login': {
                'max_attempts': 10,
                'window': timedelta(hours=1),
                'lockout': timedelta(minutes=30)
            },
            'register': {
                'max_attempts': 5,
                'window': timedelta(days=1),
                'lockout': timedelta(hours=6)
            },
            'reset': {
                'max_attempts': 3,
                'window': timedelta(hours=1),
                'lockout': timedelta(hours=1)
            }
        }
    
    def _get_storage_file(self, ip_address, action):
        """Get storage file for IP and action"""
        # Sanitize IP address for filename
        safe_ip = ip_address.replace(':', '_').replace('.', '_')
        return self.storage_dir / f"{action}_{safe_ip}.yaml"
    
    def check_limit(self, ip_address, action):
        """Check if IP is within rate limit"""
        if action not in self.limits:
            return True
        
        limit_config = self.limits[action]
        storage_file = self._get_storage_file(ip_address, action)
        
        # Load existing data
        if storage_file.exists():
            try:
                with open(storage_file, 'r') as f:
                    data = yaml.safe_load(f)
            except:
                data = None
        else:
            data = None
        
        if not data:
            return True
        
        # Check if in lockout period
        if 'lockout_until' in data:
            lockout_until = datetime.fromisoformat(data['lockout_until'])
            if datetime.now(timezone.utc) < lockout_until:
                return False
            else:
                # Lockout expired, reset
                data = {'attempts': [], 'lockout_until': None}
        
        # Clean old attempts
        window_start = datetime.now(timezone.utc) - limit_config['window']
        data['attempts'] = [
            attempt for attempt in data.get('attempts', [])
            if datetime.fromisoformat(attempt) > window_start
        ]
        
        # Check attempt count
        if len(data['attempts']) >= limit_config['max_attempts']:
            # Set lockout
            data['lockout_until'] = (
                datetime.now(timezone.utc) + limit_config['lockout']
            ).isoformat()
            
            # Save data
            with open(storage_file, 'w') as f:
                yaml.dump(data, f)
            
            return False
        
        return True
    
    def record_attempt(self, ip_address, action):
        """Record an attempt for rate limiting"""
        if action not in self.limits:
            return
        
        storage_file = self._get_storage_file(ip_address, action)
        
        # Load existing data
        if storage_file.exists():
            try:
                with open(storage_file, 'r') as f:
                    data = yaml.safe_load(f)
            except:
                data = {'attempts': []}
        else:
            data = {'attempts': []}
        
        # Add new attempt
        data['attempts'].append(datetime.now(timezone.utc).isoformat())
        
        # Save data
        with open(storage_file, 'w') as f:
            yaml.dump(data, f)
    
    def cleanup_old_records(self):
        """Clean up old rate limit records"""
        for storage_file in self.storage_dir.glob("*.yaml"):
            try:
                with open(storage_file, 'r') as f:
                    data = yaml.safe_load(f)
                
                # Check if file has any recent activity
                has_recent = False
                
                if 'lockout_until' in data and data['lockout_until']:
                    lockout_until = datetime.fromisoformat(data['lockout_until'])
                    if datetime.now(timezone.utc) < lockout_until:
                        has_recent = True
                
                if not has_recent and 'attempts' in data:
                    # Check if any attempts are recent (within last day)
                    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
                    for attempt in data['attempts']:
                        if datetime.fromisoformat(attempt) > day_ago:
                            has_recent = True
                            break
                
                if not has_recent:
                    storage_file.unlink()
                    
            except:
                # Remove corrupted files
                storage_file.unlink()
    
    def get_status(self, ip_address=None):
        """Get rate limit status for IP or all IPs"""
        status = {}
        
        if ip_address:
            # Get status for specific IP
            for action in self.limits:
                storage_file = self._get_storage_file(ip_address, action)
                if storage_file.exists():
                    try:
                        with open(storage_file, 'r') as f:
                            data = yaml.safe_load(f)
                        
                        limit_config = self.limits[action]
                        window_start = datetime.now(timezone.utc) - limit_config['window']
                        recent_attempts = [
                            attempt for attempt in data.get('attempts', [])
                            if datetime.fromisoformat(attempt) > window_start
                        ]
                        
                        status[action] = {
                            'attempts': len(recent_attempts),
                            'max_attempts': limit_config['max_attempts'],
                            'lockout_until': data.get('lockout_until'),
                            'window': str(limit_config['window'])
                        }
                    except:
                        pass
        else:
            # Get overall status
            for storage_file in self.storage_dir.glob("*.yaml"):
                try:
                    # Parse filename
                    filename = storage_file.stem
                    parts = filename.split('_', 1)
                    if len(parts) == 2:
                        action, safe_ip = parts
                        
                        with open(storage_file, 'r') as f:
                            data = yaml.safe_load(f)
                        
                        if action in self.limits:
                            limit_config = self.limits[action]
                            window_start = datetime.now(timezone.utc) - limit_config['window']
                            recent_attempts = [
                                attempt for attempt in data.get('attempts', [])
                                if datetime.fromisoformat(attempt) > window_start
                            ]
                            
                            if recent_attempts or data.get('lockout_until'):
                                if safe_ip not in status:
                                    status[safe_ip] = {}
                                
                                status[safe_ip][action] = {
                                    'attempts': len(recent_attempts),
                                    'max_attempts': limit_config['max_attempts'],
                                    'lockout_until': data.get('lockout_until')
                                }
                except:
                    pass
        
        return status