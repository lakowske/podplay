# Logging Specification for Podplay Services

## Overview

This document defines the standardized logging architecture for all Podplay services, ensuring consistent log management, persistence, and observability across Apache, Mail, DNS, and Certificate services.

## Current Logging Analysis

### Existing Patterns Identified

**DNS Service (BIND)** - Most mature logging setup:
- Dual-channel logging: default + query logs
- Log rotation: 3 versions, 5MB each
- Structured format with timestamps, severity, categories
- Directory: `/var/log/bind/`

**Mail Service (Postfix/Dovecot)**:
- Dovecot: Dual logging (`/var/log/dovecot.log`, `/var/log/dovecot-info.log`)
- Postfix: System logging via `/var/log/mail.log`
- Container tails mail.log for stdout

**Apache Service**:
- Currently uses default foreground logging
- No persistent file logging configured

## Standardized Logging Architecture

### 1. Dual Logging Strategy

All services implement **dual logging**:
- **Container Logs**: stdout/stderr for container orchestration
- **Persistent File Logs**: Volume-mounted files for long-term storage and analysis

### 2. Volume Mount Strategy

Following project best practices using **named volumes**:

```bash
# Create shared log volume
podman volume create service-logs

# Mount in containers
-v service-logs:/var/log/services
```

**Directory Structure**:
```
/var/log/services/
├── apache/
│   ├── access.log
│   ├── error.log
│   └── ssl_request.log
├── mail/
│   ├── dovecot.log
│   ├── dovecot-info.log
│   ├── postfix.log
│   └── mail.log
├── dns/
│   ├── default.log
│   ├── query.log
│   └── security.log
└── certificates/
    ├── certbot.log
    └── operations.log
```

### 3. Log Rotation and Retention

**Standard Rotation Policy**:
- Size-based rotation: 10MB per file
- Keep 5 versions of each log
- Compress rotated logs
- Daily cleanup of logs older than 30 days

**Implementation**:
```bash
# In service configurations
file "/var/log/services/[service]/[logfile].log" versions 5 size 10m;
```

### 4. Log Formats

#### Standard Format Components
All logs include:
- **Timestamp**: ISO 8601 format (`2024-01-15T10:30:45Z`)
- **Severity**: ERROR, WARN, INFO, DEBUG
- **Service**: Service identifier (apache, mail, dns, cert)
- **Category**: Log category (access, error, security, operation)
- **Message**: Structured log message

#### Service-Specific Formats

**Apache Logs**:
```apache
# Access Log (Combined + Response Time)
LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\" %D" combined_with_time

# Error Log
ErrorLogFormat "[%{u}t] [%-m:%l] [pid %P:tid %T] %7F: %E: [client\ %a] %M% ,\ referer\ %{Referer}i"
```

**Mail Logs**:
```
# Postfix format (existing syslog format maintained)
Jan 15 10:30:45 mail postfix/smtpd[1234]: connect from unknown[192.168.1.100]

# Dovecot format (configured format)
2024-01-15 10:30:45 Info: [service=imap] [user=admin@lab.sethlakowske.com] Login: user=<admin@lab.sethlakowske.com>
```

**DNS Logs**:
```
# Query Log
15-Jan-2024 10:30:45.123 client @0x7f8b8c000960 192.168.1.100#52341 (example.com): query: example.com IN A +E(0)EDC (192.168.1.1)

# Default Log
15-Jan-2024 10:30:45.123 general: info: zone lab.sethlakowske.com/IN: loaded serial 2024011501
```

## Service Implementation Guidelines

### Apache Service

**Configuration Updates**:
```apache
# In virtual host configurations
ErrorLog /var/log/services/apache/error.log
CustomLog /var/log/services/apache/access.log combined_with_time
LogLevel info ssl:warn

# SSL-specific logging
<IfModule mod_ssl.c>
    CustomLog /var/log/services/apache/ssl_request.log \
              "%t %h %{SSL_PROTOCOL}x %{SSL_CIPHER}x \"%r\" %b"
</IfModule>
```

**Container Updates**:
```dockerfile
# Create log directory
RUN mkdir -p /var/log/services/apache

# In entrypoint script
# Enable dual logging - both file and stdout
tail -F /var/log/services/apache/error.log &
tail -F /var/log/services/apache/access.log &
```

### Mail Service

**Dovecot Configuration** (already well-configured):
```
# Update paths to standardized locations
log_path = /var/log/services/mail/dovecot.log
info_log_path = /var/log/services/mail/dovecot-info.log
debug_log_path = /var/log/services/mail/dovecot-debug.log
```

**Postfix Configuration**:
```
# Route Postfix logs to dedicated file
maillog_file = /var/log/services/mail/postfix.log
```

**Container Updates**:
```bash
# In mail-entrypoint.sh
mkdir -p /var/log/services/mail

# Tail multiple logs for container output
tail -F /var/log/services/mail/dovecot.log \
     /var/log/services/mail/postfix.log \
     /var/log/mail.log 2>/dev/null &
```

### DNS Service

**BIND Configuration** (enhance existing):
```
logging {
    channel default_log {
        file "/var/log/services/dns/default.log" versions 5 size 10m;
        severity info;
        print-time yes;
        print-severity yes;
        print-category yes;
    };
    
    channel query_log {
        file "/var/log/services/dns/query.log" versions 5 size 10m;
        severity info;
        print-time yes;
    };
    
    channel security_log {
        file "/var/log/services/dns/security.log" versions 5 size 10m;
        severity warning;
        print-time yes;
        print-severity yes;
    };
    
    category default { default_log; };
    category queries { query_log; };
    category security { security_log; };
    category lame-servers { null; };
};
```

### Certificate Service

**New Logging for Certbot**:
```bash
# In certbot-entrypoint.sh
LOG_DIR="/var/log/services/certificates"
mkdir -p "$LOG_DIR"

# Function for structured logging
log_operation() {
    local level="$1"
    local category="$2"
    local message="$3"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    echo "[$timestamp] [$level] [certbot:$category] $message" | tee -a "$LOG_DIR/operations.log"
}

# Usage examples
log_operation "INFO" "certificate" "Starting certificate generation for $DOMAIN"
log_operation "ERROR" "validation" "Failed to validate domain $DOMAIN"
```

## Container Orchestration Integration

### Podman Compose Example

```yaml
version: '3.8'

volumes:
  service-logs:
    driver: local
  certs:
    driver: local

services:
  apache:
    image: podplay-apache-debian:latest
    volumes:
      - service-logs:/var/log/services
      - certs:/data/certificates
    ports:
      - "8080:80"
      - "8443:443"
    
  mail:
    image: podplay-mail-debian:latest
    volumes:
      - service-logs:/var/log/services
      - certs:/data/certificates
    ports:
      - "25:25"
      - "587:587"
      - "993:993"
    
  dns:
    image: podplay-bind-debian:latest
    volumes:
      - service-logs:/var/log/services
    ports:
      - "53:53/tcp"
      - "53:53/udp"
```

### Log Collection and Monitoring

**Log Aggregation Commands**:
```bash
# View all service logs
podman exec -it <container> tail -f /var/log/services/*/*

# Service-specific logs
podman exec -it apache-container tail -f /var/log/services/apache/access.log

# Search across all logs
podman exec -it <container> grep -r "ERROR" /var/log/services/
```

**Log Analysis Queries**:
```bash
# Find SSL/TLS errors across services
grep -r "SSL\|TLS.*error" /var/log/services/

# Monitor certificate operations
tail -f /var/log/services/certificates/operations.log

# Track DNS security events
tail -f /var/log/services/dns/security.log
```

## Security Considerations

### File Permissions
```bash
# Log directories - readable by service users
chmod 755 /var/log/services/
chmod 755 /var/log/services/*/

# Log files - writable by service, readable by log group
chmod 644 /var/log/services/*/*.log
chown service-user:log-group /var/log/services/*/*.log
```

### Log Sanitization
- **Sensitive Data**: Automatically redact passwords, tokens, private keys
- **PII**: Mask IP addresses in non-security logs when required
- **Certificate Data**: Log certificate metadata, never private keys

### Access Control
- Service containers: Read/write access to own logs only
- Monitoring containers: Read-only access to all logs
- Log rotation: Automated cleanup of expired logs

## Troubleshooting Guide

### Common Log Locations
```bash
# Container stdout/stderr
podman logs <container-name>

# Persistent service logs
/var/log/services/<service-name>/

# System integration
journalctl -u <service-name>
```

### Log Verification
```bash
# Verify log rotation is working
ls -la /var/log/services/*/
find /var/log/services/ -name "*.log.*" -type f

# Check log file permissions
stat /var/log/services/*/*.log

# Monitor log growth
du -sh /var/log/services/*/
```

### Performance Impact
- **Disk Space**: Monitor log volume usage
- **I/O**: Use log buffering for high-traffic services
- **Network**: Consider log shipping for production deployments

## Implementation Checklist

- [ ] Create `service-logs` named volume
- [ ] Update Apache configuration for file logging
- [ ] Enhance mail service logging paths
- [ ] Verify DNS logging configuration
- [ ] Add certificate service logging
- [ ] Update container entrypoint scripts
- [ ] Test log rotation functionality
- [ ] Verify dual logging (file + container)
- [ ] Document log monitoring procedures
- [ ] Create log analysis scripts

This specification provides a consistent, scalable logging infrastructure that aligns with the existing service architecture while enhancing observability and maintainability across all Podplay services.