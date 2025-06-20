#!/usr/bin/env python3
import os
import sys
import time
import argparse
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
    parser = argparse.ArgumentParser(description='Certificate management tool')
    parser.add_argument('path', help='Path to search for certificates')
    parser.add_argument('--watch', '-w', action='store_true', 
                        help='Watch for changes in certificates (uses file system events)')
    
    args = parser.parse_args()
    
    if args.watch:
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