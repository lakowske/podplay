#!/data/.venv/bin/python3
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from session import SessionManager
from rate_limit import RateLimiter

def cleanup_expired_registrations():
    """Clean up expired registration tokens"""
    pending_dir = Path("/data/user-data/pending/registrations")
    if not pending_dir.exists():
        return 0
    
    count = 0
    for token_file in pending_dir.glob("*.yaml"):
        try:
            import yaml
            with open(token_file, "r") as f:
                data = yaml.safe_load(f)
            
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now(timezone.utc) > expires_at:
                token_file.unlink()
                count += 1
        except:
            # Remove corrupted files
            token_file.unlink()
            count += 1
    
    return count

def cleanup_expired_resets():
    """Clean up expired password reset tokens"""
    pending_dir = Path("/data/user-data/pending/resets")
    if not pending_dir.exists():
        return 0
    
    count = 0
    for token_file in pending_dir.glob("*.yaml"):
        try:
            import yaml
            with open(token_file, "r") as f:
                data = yaml.safe_load(f)
            
            expires_at = datetime.fromisoformat(data['expires_at'])
            if datetime.now(timezone.utc) > expires_at:
                token_file.unlink()
                count += 1
        except:
            # Remove corrupted files
            token_file.unlink()
            count += 1
    
    return count

def main():
    parser = argparse.ArgumentParser(description="Clean up expired authentication data")
    parser.add_argument("--sessions", action="store_true", help="Clean up expired sessions")
    parser.add_argument("--registrations", action="store_true", help="Clean up expired registrations")
    parser.add_argument("--resets", action="store_true", help="Clean up expired password resets")
    parser.add_argument("--rate-limits", action="store_true", help="Clean up old rate limit data")
    parser.add_argument("--all", action="store_true", help="Clean up all expired data")
    
    args = parser.parse_args()
    
    if not any([args.sessions, args.registrations, args.resets, args.rate_limits, args.all]):
        args.all = True
    
    print("Starting cleanup...")
    
    if args.sessions or args.all:
        session_mgr = SessionManager()
        session_mgr.cleanup_expired_sessions()
        print("✓ Cleaned up expired sessions")
    
    if args.registrations or args.all:
        count = cleanup_expired_registrations()
        print(f"✓ Cleaned up {count} expired registration tokens")
    
    if args.resets or args.all:
        count = cleanup_expired_resets()
        print(f"✓ Cleaned up {count} expired password reset tokens")
    
    if args.rate_limits or args.all:
        rate_limiter = RateLimiter()
        rate_limiter.cleanup_old_records()
        print("✓ Cleaned up old rate limit records")
    
    print("Cleanup completed!")

if __name__ == "__main__":
    main()