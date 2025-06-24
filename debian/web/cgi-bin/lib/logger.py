#!/usr/bin/env python3
"""
Centralized logging for CGI scripts with dual output and structured formatting
"""

import logging
import sys
import traceback
import json
from datetime import datetime, timezone
from pathlib import Path

class CGILogger:
    """Enhanced logger for CGI scripts with structured output and dual logging"""
    
    def __init__(self, script_name):
        self.script_name = script_name
        self.setup_logging()
    
    def setup_logging(self):
        """Configure dual logging: structured file logs + Apache error log"""
        log_dir = Path("/data/logs/apache")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create custom formatter for structured logs
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [CGI-%(name)s]: %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S%z'
        )
        
        # File handler for structured CGI errors
        file_handler = logging.FileHandler(log_dir / "cgi-errors.log")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # Stream handler for Apache error log (stderr) - DISABLED for CGI
        # stderr_handler = logging.StreamHandler(sys.stderr)
        # stderr_handler.setFormatter(formatter)
        # stderr_handler.setLevel(logging.WARNING)  # Only warnings/errors to Apache log
        
        # Configure logger
        self.logger = logging.getLogger(self.script_name)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        # self.logger.addHandler(stderr_handler)  # Disabled for CGI
        
        # Prevent duplicate logs from root logger
        self.logger.propagate = False
    
    def _create_context(self, user_email=None, client_ip=None, extra=None):
        """Create structured context for log entries"""
        context = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'script': self.script_name,
            'user': user_email or 'anonymous',
            'client_ip': client_ip or 'unknown'
        }
        if extra:
            context.update(extra)
        return context
    
    def log_info(self, message, user_email=None, client_ip=None, extra=None):
        """Log informational messages"""
        context = self._create_context(user_email, client_ip, extra)
        self.logger.info(f"{message} | Context: {json.dumps(context, separators=(',', ':'))}")
    
    def log_warning(self, message, user_email=None, client_ip=None, extra=None):
        """Log warning messages"""
        context = self._create_context(user_email, client_ip, extra)
        self.logger.warning(f"{message} | Context: {json.dumps(context, separators=(',', ':'))}")
    
    def log_error(self, message, exception=None, user_email=None, client_ip=None, extra=None):
        """Log error messages with optional exception details"""
        context = self._create_context(user_email, client_ip, extra)
        
        if exception:
            context['exception_type'] = type(exception).__name__
            context['exception_message'] = str(exception)
        
        self.logger.error(f"{message} | Context: {json.dumps(context, separators=(',', ':'))}")
        
        # Log full stack trace for debugging
        if exception:
            self.logger.error(f"Stack trace for {self.script_name}: {traceback.format_exc()}")
    
    def log_security_event(self, event_type, message, user_email=None, client_ip=None, extra=None):
        """Log security-related events with special marking"""
        context = self._create_context(user_email, client_ip, extra)
        context['security_event'] = event_type
        
        # Log to both file and stderr for security events
        log_message = f"SECURITY-{event_type.upper()}: {message} | Context: {json.dumps(context, separators=(',', ':'))}"
        self.logger.warning(log_message)
        
        # Also write to security-specific log
        try:
            security_log = Path("/data/logs/apache") / "security.log"
            with open(security_log, "a") as f:
                f.write(f"[{context['timestamp']}] {log_message}\n")
        except Exception:
            pass  # Don't fail if security log write fails

# Custom exception classes for better error categorization
class CGIError(Exception):
    """Base class for CGI-specific errors"""
    pass

class ValidationError(CGIError):
    """User input validation errors - safe to show to user"""
    pass

class AuthenticationError(CGIError):
    """Authentication/authorization errors"""
    pass

class RateLimitError(CGIError):
    """Rate limiting errors"""
    pass

class ConfigurationError(CGIError):
    """System configuration errors"""
    pass