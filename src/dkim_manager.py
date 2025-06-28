#!/usr/bin/env python3
"""DKIM key management tool with hot-reload capabilities for BIND DNS service."""
import os
import re
import time
import argparse
import subprocess
import logging
import sys
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
LOG_LEVEL = os.environ.get('PODPLAY_DKIM_LOG_LEVEL', os.environ.get('PODPLAY_LOG_LEVEL', 'INFO'))
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='[%(asctime)s] [%(levelname)s] [DKIM-MANAGER] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class DKIMKeyEventHandler(FileSystemEventHandler):
    """Handle file system events for DKIM key files."""
    
    def __init__(self, reload_strategy):
        self.reload_strategy = reload_strategy
        self.dkim_files = {'default.txt', 'default.private'}
        self.pending_reloads = {}
        self.debounce_seconds = 2
    
    def is_dkim_file(self, path):
        """Check if a file is a DKIM key file."""
        return Path(path).name in self.dkim_files
    
    def get_domain_from_path(self, path):
        """Extract domain name from DKIM key path."""
        # Path format: /data/user-data/dkim/domain.com/default.txt
        path_parts = Path(path).parts
        if 'dkim' in path_parts:
            dkim_index = path_parts.index('dkim')
            if dkim_index + 1 < len(path_parts) - 1:
                return path_parts[dkim_index + 1]
        return None
    
    def on_created(self, event):
        if not event.is_directory and self.is_dkim_file(event.src_path):
            domain = self.get_domain_from_path(event.src_path)
            if domain:
                logger.info(f"New DKIM key detected for domain: {domain}")
                self.schedule_reload(domain, event.src_path)
    
    def on_modified(self, event):
        if not event.is_directory and self.is_dkim_file(event.src_path):
            domain = self.get_domain_from_path(event.src_path)
            if domain:
                logger.info(f"DKIM key modified for domain: {domain}")
                self.schedule_reload(domain, event.src_path)
    
    def schedule_reload(self, domain, file_path):
        """Schedule a debounced reload for the domain."""
        self.pending_reloads[domain] = time.time()
        
        def delayed_reload():
            time.sleep(self.debounce_seconds)
            if domain in self.pending_reloads:
                del self.pending_reloads[domain]
                self.handle_dkim_change(domain)
        
        import threading
        thread = threading.Thread(target=delayed_reload)
        thread.daemon = True
        thread.start()
    
    def handle_dkim_change(self, domain):
        """Process DKIM key change for a domain."""
        try:
            logger.info(f"Processing DKIM key change for domain: {domain}")
            
            # Check if both key files exist
            dkim_dir = Path(f"/data/user-data/dkim/{domain}")
            txt_file = dkim_dir / "default.txt"
            key_file = dkim_dir / "default.private"
            
            if not txt_file.exists() or not key_file.exists():
                logger.warning(f"DKIM keys not complete for {domain}, waiting...")
                return
            
            # Extract public key from default.txt
            public_key = self.reload_strategy.extract_dkim_public_key(txt_file)
            if not public_key:
                logger.error(f"Failed to extract DKIM public key for {domain}")
                return
            
            # Update DNS zone
            success = self.reload_strategy.update_zone_with_dkim(domain, public_key)
            
            if success:
                logger.info(f"Successfully updated DNS zone with DKIM key for {domain}")
            else:
                logger.error(f"Failed to update DNS zone for {domain}")
                
        except Exception as e:
            logger.error(f"DKIM reload error for {domain}: {e}")


class BindDKIMReloadStrategy:
    """BIND-specific DKIM reload strategy."""
    
    def __init__(self):
        self.zone_dir = "/etc/bind/zones"
        self.backup_dir = "/tmp/zone-backup"
        self.ensure_backup_dir()
    
    def ensure_backup_dir(self):
        """Ensure backup directory exists."""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def extract_dkim_public_key(self, txt_file):
        """Extract the public key value from DKIM TXT file."""
        try:
            with open(txt_file, 'r') as f:
                content = f.read()
            
            # Extract the p= value from the TXT record
            # Handle multi-line format with quotes
            lines = content.strip().split('\n')
            key_parts = []
            
            for line in lines:
                # Remove quotes and extract content
                match = re.search(r'"([^"]+)"', line)
                if match:
                    key_parts.append(match.group(1))
            
            # Join all parts
            full_record = ''.join(key_parts)
            
            # Extract just the p= value
            p_match = re.search(r'p=([A-Za-z0-9+/=]+)', full_record)
            if p_match:
                return p_match.group(1)
            
            return None
        except Exception as e:
            logger.error(f"Error reading DKIM key file: {e}")
            return None
    
    def update_zone_with_dkim(self, domain, public_key):
        """Update DNS zone file with DKIM public key."""
        zone_file = Path(self.zone_dir) / f"db.{domain}"
        
        if not zone_file.exists():
            logger.error(f"Zone file not found: {zone_file}")
            return False
        
        try:
            # Backup current zone file
            backup_file = Path(self.backup_dir) / f"db.{domain}.{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            subprocess.run(['cp', str(zone_file), str(backup_file)], check=True)
            logger.info(f"Backed up zone file: {backup_file}")
            
            # Read current zone file
            with open(zone_file, 'r') as f:
                zone_content = f.read()
            
            # Update serial number
            serial_match = re.search(r'(\d{10})\s*;\s*Serial', zone_content)
            if serial_match:
                old_serial = serial_match.group(1)
                # Increment serial
                date_part = old_serial[:8]
                seq_part = int(old_serial[8:])
                today = datetime.now().strftime('%Y%m%d')
                
                if date_part == today:
                    new_serial = f"{date_part}{seq_part + 1:02d}"
                else:
                    new_serial = f"{today}01"
                
                zone_content = zone_content.replace(old_serial, new_serial)
                logger.info(f"Updated serial: {old_serial} -> {new_serial}")
            
            # Format DKIM record for BIND (split into chunks if needed)
            if len(public_key) > 255:
                # Split long keys into 255-char chunks
                chunks = [public_key[i:i+255] for i in range(0, len(public_key), 255)]
                dkim_record = f'default._domainkey IN TXT ( "v=DKIM1; h=sha256; k=rsa; t=y; "\n'
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        dkim_record += f'    "p={chunk}"\n'
                    else:
                        dkim_record += f'    "{chunk}"\n'
                dkim_record += '    )'
            else:
                dkim_record = f'default._domainkey IN TXT "v=DKIM1; h=sha256; k=rsa; t=y; p={public_key}"'
            
            # Check if DKIM record already exists or has placeholder
            if 'default._domainkey' in zone_content or 'DKIM - Domain Keys Identified Mail' in zone_content:
                # Replace the entire DKIM section (including comments and placeholders)
                # Pattern matches the DKIM comment section and any existing record
                dkim_section_pattern = r'; DKIM - Domain Keys Identified Mail[^\n]*\n(?:; [^\n]*\n)*(?:default\._domainkey[^\n]*\n)?'
                
                replacement = f'; DKIM - Domain Keys Identified Mail\n{dkim_record}\n'
                
                if re.search(dkim_section_pattern, zone_content, re.MULTILINE):
                    zone_content = re.sub(
                        dkim_section_pattern,
                        replacement,
                        zone_content,
                        flags=re.MULTILINE
                    )
                    logger.info("Replaced existing DKIM record")
                else:
                    # Fallback: find any line with DKIM and replace the whole section manually
                    lines = zone_content.split('\n')
                    new_lines = []
                    in_dkim_section = False
                    dkim_section_added = False
                    
                    for line in lines:
                        if 'DKIM - Domain Keys Identified Mail' in line:
                            in_dkim_section = True
                            new_lines.append('; DKIM - Domain Keys Identified Mail')
                            new_lines.append(dkim_record)
                            dkim_section_added = True
                            continue
                        elif in_dkim_section and (line.startswith(';') or 'default._domainkey' in line):
                            # Skip comment lines and existing DKIM records in this section
                            continue
                        elif in_dkim_section and line.strip() == '':
                            in_dkim_section = False
                            new_lines.append(line)
                        else:
                            new_lines.append(line)
                    
                    zone_content = '\n'.join(new_lines)
                    logger.info("Replaced DKIM section using fallback method")
            else:
                # Add DKIM record before mail-related records section
                insert_point = zone_content.find('; Additional mail-related records')
                if insert_point == -1:
                    # Fall back to end of file
                    zone_content = zone_content.rstrip() + f'\n\n; DKIM - Domain Keys Identified Mail\n{dkim_record}\n'
                else:
                    zone_content = zone_content[:insert_point] + f'; DKIM - Domain Keys Identified Mail\n{dkim_record}\n\n' + zone_content[insert_point:]
                logger.info("Added new DKIM record")
            
            # Write updated zone file
            with open(zone_file, 'w') as f:
                f.write(zone_content)
            
            # Validate zone file
            result = subprocess.run(
                ['named-checkzone', domain, str(zone_file)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Zone validation failed: {result.stderr}")
                # Restore backup
                subprocess.run(['cp', str(backup_file), str(zone_file)], check=True)
                return False
            
            # Reload zone
            result = subprocess.run(
                ['rndc', 'reload', domain],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully reloaded zone for {domain}")
                return True
            else:
                logger.error(f"Failed to reload zone: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating zone file: {e}")
            return False


def watch_dkim_keys():
    """Watch for DKIM key changes and update DNS zones."""
    logger.info("Starting DKIM key hot-reload monitor for BIND service")
    dkim_base_path = "/data/user-data/dkim"
    
    # Initial scan
    dkim_domains = []
    if os.path.exists(dkim_base_path):
        for domain_dir in Path(dkim_base_path).iterdir():
            if domain_dir.is_dir():
                txt_file = domain_dir / "default.txt"
                if txt_file.exists():
                    dkim_domains.append(domain_dir.name)
    
    if dkim_domains:
        logger.info(f"Found DKIM keys for {len(dkim_domains)} domains:")
        for domain in dkim_domains:
            logger.info(f"  - {domain}")
    else:
        logger.info("No DKIM keys found yet")
    
    # Set up file system observer
    reload_strategy = BindDKIMReloadStrategy()
    event_handler = DKIMKeyEventHandler(reload_strategy)
    observer = Observer()
    
    # Watch the DKIM directory
    observer.schedule(event_handler, dkim_base_path, recursive=True)
    
    # Start watching
    observer.start()
    logger.info("DKIM key hot-reload monitor active...")
    logger.info("DNS zones will automatically update when DKIM keys are added or changed")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping DKIM key monitor")
        observer.stop()
    
    observer.join()


def main():
    parser = argparse.ArgumentParser(description='DKIM key management for BIND DNS')
    parser.add_argument('--hot-reload', action='store_true',
                        help='Enable hot-reload monitoring for DKIM keys')
    
    args = parser.parse_args()
    
    if args.hot_reload:
        watch_dkim_keys()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()