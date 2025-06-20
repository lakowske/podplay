# Logging Architecture Specification

## Purpose
Define a unified logging strategy that provides dual output to both container runtime (stdout/stderr) and persistent file storage for long-term analysis and compliance.

## Scope
- Standardized logging configuration across all services
- Dual logging implementation (container runtime + persistent storage)
- Log format standardization and rotation policies
- Service-specific logging requirements
- Volume management and permission models

## Requirements

### Functional Requirements
1. All services output logs to both stdout/stderr and persistent files
2. Centralized log storage in `/data/logs` volume
3. Structured log formats with consistent timestamps
4. Log rotation and retention policies
5. Service isolation within log directory structure

### Non-Functional Requirements
1. Minimal performance impact on services
2. Configurable log levels for debugging/production
3. Secure log storage with appropriate permissions
4. Integration with existing container orchestration
5. Support for log aggregation and analysis tools

## Design Decisions

### Volume Strategy
```
Named Volume: logs
Mount Point: /data/logs
Structure:
/data/logs/
├── apache/
│   ├── access.log
│   ├── error.log
│   └── ssl.log
├── bind/
│   ├── general.log
│   ├── queries.log
│   └── security.log
├── mail/
│   ├── postfix.log
│   ├── dovecot.log
│   └── auth.log
└── certbot/
    ├── operations.log
    └── errors.log
```

### Permission Model
```bash
# Log directory ownership
chown -R loguser:loggroup /data/logs
chmod 755 /data/logs
chmod 755 /data/logs/*/
chmod 644 /data/logs/*/*.log

# Service-specific permissions
User/Group: loguser:loggroup (UID 9998, GID 9998)
Services added to loggroup for write access
```

### Log Format Standards
```
Timestamp: ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ)
Severity: ERROR, WARN, INFO, DEBUG
Format: [TIMESTAMP] [SEVERITY] [SERVICE] [COMPONENT]: MESSAGE
Example: [2024-01-20T10:30:45.123Z] [INFO] [APACHE] [SSL]: Certificate loaded successfully
```

## Implementation Guidelines

### Base Logging Infrastructure

#### Dockerfile Updates
```dockerfile
# Add to base-debian Dockerfile
RUN groupadd -g 9998 loggroup && \
    useradd -u 9998 -g loggroup -M -s /usr/sbin/nologin loguser

# Create log directory structure
RUN mkdir -p /data/logs/{apache,bind,mail,certbot} && \
    chown -R loguser:loggroup /data/logs && \
    chmod 755 /data/logs /data/logs/*
```

#### Service User Configuration
```dockerfile
# Add service users to loggroup
RUN usermod -a -G loggroup www-data      # Apache
RUN usermod -a -G loggroup bind          # BIND
RUN usermod -a -G loggroup postfix       # Mail
RUN usermod -a -G loggroup dovecot       # Mail
RUN usermod -a -G loggroup certuser      # Certbot
```

### Log Rotation Configuration

#### Global Logrotate Configuration
```bash
# /etc/logrotate.d/podplay-services
/data/logs/*/*.log {
    daily
    rotate 30
    size 10M
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    create 644 loguser loggroup
}
```

#### Service-Specific Rotation
```bash
# /etc/logrotate.d/apache-logs
/data/logs/apache/*.log {
    daily
    rotate 30
    size 10M
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/podman exec apache /usr/sbin/apache2ctl graceful > /dev/null 2>&1 || true
    endscript
}
```

## Service-Specific Implementation

### Apache Web Server

#### Apache Configuration
```apache
# Custom log format with structured output
LogFormat "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [INFO] [APACHE] [ACCESS]: %h %l %u \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %D" combined_structured

LogFormat "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [ERROR] [APACHE] [ERROR]: [pid %P] [client %a] %M" error_structured

# Dual logging configuration
CustomLog /data/logs/apache/access.log combined_structured
CustomLog "|/usr/bin/tee -a /data/logs/apache/access.log" combined_structured env=!dontlog

ErrorLog /data/logs/apache/error.log
ErrorLog "|/usr/bin/tee -a /data/logs/apache/error.log"

# SSL specific logging
<IfModule mod_ssl.c>
    CustomLog /data/logs/apache/ssl.log "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [INFO] [APACHE] [SSL]: %h %{SSL_PROTOCOL}x %{SSL_CIPHER}x \"%r\" %>s"
    CustomLog "|/usr/bin/tee -a /data/logs/apache/ssl.log" "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [INFO] [APACHE] [SSL]: %h %{SSL_PROTOCOL}x %{SSL_CIPHER}x \"%r\" %>s"
</IfModule>
```

#### Apache Entrypoint Logging
```bash
# In Apache entrypoint.sh
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [APACHE] [INIT]: Initializing logging..." | tee -a /data/logs/apache/error.log
    
    # Ensure log files exist
    touch /data/logs/apache/{access,error,ssl}.log
    chown www-data:loggroup /data/logs/apache/*.log
    chmod 644 /data/logs/apache/*.log
    
    echo "[$(date -Iseconds)] [INFO] [APACHE] [INIT]: Logging initialized" | tee -a /data/logs/apache/error.log
}
```

### BIND DNS Server

#### Enhanced BIND Logging
```bash
# named.conf logging configuration
logging {
    channel stdout_log {
        stderr;
        severity info;
        print-time yes;
        print-severity yes;
        print-category yes;
    };
    
    channel general_log {
        file "/data/logs/bind/general.log" versions 5 size 10m;
        severity info;
        print-time yes;
        print-severity yes;
        print-category yes;
    };
    
    channel query_log {
        file "/data/logs/bind/queries.log" versions 5 size 20m;
        severity info;
        print-time yes;
    };
    
    channel security_log {
        file "/data/logs/bind/security.log" versions 5 size 10m;
        severity warning;
        print-time yes;
        print-severity yes;
    };
    
    # Dual output: both stdout and files
    category default { stdout_log; general_log; };
    category queries { stdout_log; query_log; };
    category security { stdout_log; security_log; };
    category lame-servers { null; };
};
```

#### BIND Entrypoint Logging
```bash
# In BIND entrypoint.sh
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [BIND] [INIT]: Initializing DNS logging..."
    
    # Create log files with proper permissions
    touch /data/logs/bind/{general,queries,security}.log
    chown bind:loggroup /data/logs/bind/*.log
    chmod 644 /data/logs/bind/*.log
    
    echo "[$(date -Iseconds)] [INFO] [BIND] [INIT]: DNS logging initialized"
}
```

### Mail Server (Postfix + Dovecot)

#### Postfix Logging Configuration
```bash
# main.cf additions for dual logging
# Postfix logs to syslog, we'll redirect and duplicate

# Custom postfix logging script
#!/bin/bash
# /usr/local/bin/postfix-logger.sh
while IFS= read -r line; do
    timestamp=$(date -Iseconds)
    echo "[$timestamp] [INFO] [MAIL] [POSTFIX]: $line" | tee -a /data/logs/mail/postfix.log
    echo "[$timestamp] [INFO] [MAIL] [POSTFIX]: $line" >&2
done
```

#### Dovecot Logging Configuration
```bash
# dovecot.conf logging section
log_path = /data/logs/mail/dovecot.log
info_log_path = /data/logs/mail/dovecot-info.log
debug_log_path = /data/logs/mail/dovecot-debug.log

# Duplicate to stdout/stderr
log_timestamp = "%Y-%m-%dT%H:%M:%S.%3N%z"

# Custom log format
login_log_format_elements = user=<%u> method=%m rip=%r lip=%l mpid=%e %c %k
```

#### Mail Entrypoint Logging
```bash
# In mail entrypoint.sh
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Initializing mail logging..." | tee -a /data/logs/mail/postfix.log
    
    # Create log files
    touch /data/logs/mail/{postfix,dovecot,dovecot-info,auth}.log
    chown postfix:loggroup /data/logs/mail/postfix.log
    chown dovecot:loggroup /data/logs/mail/dovecot*.log
    chmod 644 /data/logs/mail/*.log
    
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Mail logging initialized" | tee -a /data/logs/mail/postfix.log
}

# Tail system mail log and redirect to our structured log
tail_mail_logs() {
    tail -F /var/log/mail.log 2>/dev/null | while IFS= read -r line; do
        timestamp=$(date -Iseconds)
        echo "[$timestamp] [INFO] [MAIL] [SYSTEM]: $line" | tee -a /data/logs/mail/postfix.log
    done &
}
```

### Certificate Management (Certbot)

#### Certbot Logging Implementation
```bash
# In certbot entrypoint.sh
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [CERTBOT] [INIT]: Starting certificate operation..." | tee -a /data/logs/certbot/operations.log
    
    touch /data/logs/certbot/{operations,errors}.log
    chown certuser:loggroup /data/logs/certbot/*.log
    chmod 644 /data/logs/certbot/*.log
}

log_operation() {
    local level=$1
    local message=$2
    local timestamp=$(date -Iseconds)
    local log_entry="[$timestamp] [$level] [CERTBOT] [OPERATION]: $message"
    
    echo "$log_entry" | tee -a /data/logs/certbot/operations.log
    
    if [ "$level" = "ERROR" ]; then
        echo "$log_entry" | tee -a /data/logs/certbot/errors.log >&2
    fi
}

# Usage examples
log_operation "INFO" "Starting certificate generation for ${DOMAIN}"
log_operation "ERROR" "Failed to validate domain ownership"
```

## Container Integration

### Volume Mount Pattern
```bash
# Create logs volume
podman volume create logs

# Service with logging volume
podman run -d \
    --name apache \
    -v logs:/data/logs \
    -v certs:/data/certificates:ro \
    -p 8080:80 -p 8443:443 \
    -e DOMAIN=example.com \
    podplay-apache-debian:latest
```

### Docker Compose Integration
```yaml
version: '3.8'

volumes:
  logs:
    name: podplay-logs
  certs:
    name: podplay-certs

services:
  apache:
    image: podplay-apache-debian:latest
    volumes:
      - logs:/data/logs
      - certs:/data/certificates:ro
    ports:
      - "8080:80"
      - "8443:443"
    environment:
      - DOMAIN=example.com
      - LOG_LEVEL=info
    
  bind:
    image: podplay-bind-debian:latest
    volumes:
      - logs:/data/logs
    ports:
      - "53:53/tcp"
      - "53:53/udp"
    environment:
      - DOMAIN=example.com
      - LOG_LEVEL=info
```

### Health Check Integration
```dockerfile
# Health check with logging
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health 2>&1 | tee -a /data/logs/apache/health.log || exit 1
```

## Log Analysis and Monitoring

### Log Aggregation
```bash
# Centralized log collection script
#!/bin/bash
# collect-logs.sh

VOLUME_PATH="/var/lib/containers/storage/volumes/logs/_data"
ARCHIVE_DIR="/backup/logs/$(date +%Y%m%d)"

mkdir -p "$ARCHIVE_DIR"

# Compress and archive logs
tar -czf "$ARCHIVE_DIR/apache-logs.tar.gz" -C "$VOLUME_PATH" apache/
tar -czf "$ARCHIVE_DIR/bind-logs.tar.gz" -C "$VOLUME_PATH" bind/
tar -czf "$ARCHIVE_DIR/mail-logs.tar.gz" -C "$VOLUME_PATH" mail/
tar -czf "$ARCHIVE_DIR/certbot-logs.tar.gz" -C "$VOLUME_PATH" certbot/
```

### Log Monitoring Examples
```bash
# Real-time error monitoring
tail -f /var/lib/containers/storage/volumes/logs/_data/*/error*.log | grep ERROR

# Service-specific monitoring
journalctl -f CONTAINER_NAME=apache
journalctl -f CONTAINER_NAME=bind

# Log analysis commands
grep "ERROR" /var/lib/containers/storage/volumes/logs/_data/*/*.log
grep "$(date +%Y-%m-%d)" /var/lib/containers/storage/volumes/logs/_data/apache/access.log | wc -l
```

## Performance Considerations

### Asynchronous Logging
```bash
# Use syslog for high-volume logging
logger -t "APACHE" -p local0.info "High volume message"

# Buffer configuration for high throughput
echo "net.core.rmem_max = 16777216" >> /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" >> /etc/sysctl.conf
```

### Log Level Management
```bash
# Environment-based log level control
LOG_LEVEL=${LOG_LEVEL:-info}

case $LOG_LEVEL in
    debug)   APACHE_LOG_LEVEL="debug" ;;
    info)    APACHE_LOG_LEVEL="info" ;;
    warn)    APACHE_LOG_LEVEL="warn" ;;
    error)   APACHE_LOG_LEVEL="error" ;;
    *)       APACHE_LOG_LEVEL="info" ;;
esac
```

## Security Considerations

### Log Sanitization
```bash
# Sanitize sensitive data from logs
sanitize_log_entry() {
    local entry="$1"
    # Remove potential passwords, tokens, etc.
    echo "$entry" | sed -E 's/(password|token|key)=[^[:space:]]*/\1=***REDACTED***/gi'
}
```

### Log Access Control
```bash
# Restrict log access
chmod 640 /data/logs/*/*.log
chown loguser:loggroup /data/logs/*/*.log

# Audit log access
auditctl -w /data/logs -p rwxa -k log_access
```

## Testing and Validation

### Log Functionality Tests
```bash
#!/bin/bash
# test-logging.sh

# Test dual logging functionality
test_apache_logging() {
    echo "Testing Apache dual logging..."
    
    # Make test request
    curl -s http://localhost/test > /dev/null
    
    # Check container logs
    if podman logs apache | grep -q "GET /test"; then
        echo "✓ Container logging works"
    else
        echo "✗ Container logging failed"
    fi
    
    # Check persistent logs
    if grep -q "GET /test" /var/lib/containers/storage/volumes/logs/_data/apache/access.log; then
        echo "✓ Persistent logging works"
    else
        echo "✗ Persistent logging failed"
    fi
}

# Run tests for all services
test_apache_logging
test_bind_logging
test_mail_logging
```

### Log Format Validation
```bash
# Validate log format consistency
validate_log_format() {
    local log_file="$1"
    local expected_pattern="^\[[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z\] \[(ERROR|WARN|INFO|DEBUG)\] \[[A-Z]+\] \[[A-Z]+\]:"
    
    if grep -qE "$expected_pattern" "$log_file"; then
        echo "✓ Log format valid: $log_file"
    else
        echo "✗ Log format invalid: $log_file"
    fi
}
```

## Troubleshooting Guide

### Common Issues

1. **Permission Denied Errors**
   ```bash
   # Fix: Ensure proper group membership
   usermod -a -G loggroup service-user
   chmod 664 /data/logs/service/*.log
   ```

2. **Log Rotation Not Working**
   ```bash
   # Debug logrotate
   logrotate -d /etc/logrotate.d/podplay-services
   logrotate -f /etc/logrotate.d/podplay-services
   ```

3. **Disk Space Issues**
   ```bash
   # Monitor log volume usage
   podman system df
   du -sh /var/lib/containers/storage/volumes/logs/_data/
   ```

### Diagnostic Commands
```bash
# Check logging infrastructure
podman volume inspect logs
podman exec service ls -la /data/logs/
podman logs service --tail 50

# Verify dual logging
podman exec service tail -f /data/logs/service/application.log &
podman logs -f service &
```

## Future Enhancements

1. **Structured Logging**
   - JSON log format support
   - Elasticsearch integration
   - Kibana dashboards

2. **Advanced Monitoring**
   - Real-time log streaming
   - Anomaly detection
   - Alert integration

3. **Compliance Features**
   - Log integrity verification
   - Audit trail preservation
   - Regulatory compliance reports