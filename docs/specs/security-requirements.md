# Security Requirements Specification

## Purpose
Define comprehensive security requirements and implementation guidelines for all services.

## Scope
- Container security best practices
- Network security configuration
- Cryptographic standards
- Access control and authentication
- Vulnerability management

## Requirements

### Functional Requirements
1. All services run as non-root users where possible
2. TLS encryption for all external communications
3. Strong authentication mechanisms
4. Secure secret management
5. Comprehensive audit logging

### Non-Functional Requirements
1. Compliance with modern security standards
2. Minimal attack surface
3. Defense in depth architecture
4. Regular security updates
5. Incident response capabilities

## Container Security

### Non-Root Execution
```dockerfile
# Create service user
RUN groupadd -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup appuser

# Drop privileges
USER appuser

# Exception: Certbot requires root for port 80 binding
# But drops privileges after certificate generation
```

### Read-Only Root Filesystem
```dockerfile
# Enable read-only root filesystem
VOLUME ["/tmp", "/var/tmp", "/var/log"]
```

```bash
# Run with read-only filesystem
podman run --read-only \
    --tmpfs /tmp \
    --tmpfs /var/tmp \
    -v logs:/var/log \
    service:latest
```

### Resource Limits
```bash
# CPU and memory limits
podman run -d \
    --cpus="1.0" \
    --memory="512m" \
    --memory-swap="512m" \
    --ulimit nofile=1024:1024 \
    service:latest
```

### Capability Dropping
```bash
# Drop all capabilities except required ones
podman run -d \
    --cap-drop=ALL \
    --cap-add=NET_BIND_SERVICE \
    service:latest
```

## Network Security

### TLS Configuration

#### Minimum TLS Versions
```
TLS 1.2 (minimum)
TLS 1.3 (preferred)
```

#### Cipher Suites
```apache
# Apache SSL configuration
SSLProtocol -all +TLSv1.2 +TLSv1.3
SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
SSLHonorCipherOrder off
SSLSessionTickets off
```

#### Perfect Forward Secrecy
```nginx
# Nginx configuration
ssl_prefer_server_ciphers off;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
```

### Network Segmentation
```bash
# Create isolated networks
podman network create --internal backend-net
podman network create --driver bridge frontend-net

# DMZ network for public services
podman network create \
    --subnet 172.20.1.0/24 \
    --gateway 172.20.1.1 \
    dmz-net
```

### Firewall Rules
```bash
# Host firewall configuration
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow established connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow specific services
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -m conntrack --ctstate NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -m conntrack --ctstate NEW -j ACCEPT

# Rate limiting
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW -m limit --limit 3/min --limit-burst 3 -j ACCEPT
```

## Authentication and Authorization

### Service Authentication
```yaml
# Service-to-service authentication
services:
  web:
    environment:
      - SERVICE_TOKEN_FILE=/run/secrets/service_token
    secrets:
      - service_token

secrets:
  service_token:
    file: ./secrets/service_token.txt
```

### User Authentication
```apache
# Apache basic authentication
AuthType Basic
AuthName "Restricted Area"
AuthUserFile /etc/apache2/.htpasswd
Require valid-user
```

### Certificate-Based Authentication
```nginx
# Client certificate authentication
ssl_client_certificate /etc/ssl/certs/ca.crt;
ssl_verify_client on;
ssl_verify_depth 2;
```

## Secret Management

### Container Secrets
```bash
# Mount secrets as files (not environment variables)
podman run -d \
    --secret source=db_password,target=/run/secrets/db_password,mode=0400 \
    service:latest
```

### Secret Rotation
```bash
#!/bin/bash
# secret-rotation.sh

# Generate new secret
openssl rand -base64 32 > /tmp/new_secret

# Update secret in container
podman secret create db_password_new /tmp/new_secret

# Rolling update containers
podman-compose up -d --no-deps service

# Remove old secret
podman secret rm db_password_old

# Clean up
rm /tmp/new_secret
```

## Certificate Security

### Certificate Permissions
```bash
# Set restrictive permissions
chmod 640 /data/certificates/*/privkey.pem
chmod 644 /data/certificates/*/fullchain.pem
chown certuser:certgroup /data/certificates/*/*.pem
```

### Certificate Validation
```bash
# Validate certificate chain
openssl verify -CAfile ca.pem certificate.pem

# Check certificate expiry
openssl x509 -in certificate.pem -checkend 864000 # 10 days
```

### OCSP Stapling
```apache
# Apache OCSP configuration
SSLUseStapling on
SSLStaplingCache "shmcb:logs/ssl_stapling(32768)"
SSLStaplingStandardCacheTimeout 3600
SSLStaplingErrorCacheTimeout 600
```

## Security Headers

### HTTP Security Headers
```apache
# Security headers
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "DENY"
Header always set X-XSS-Protection "1; mode=block"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set Permissions-Policy "geolocation=(), microphone=(), camera=()"

# HSTS
Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"

# CSP
Header always set Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
```

### Mail Security Headers
```bash
# Postfix security configuration
smtpd_helo_required = yes
smtpd_recipient_restrictions = 
    permit_mynetworks,
    permit_sasl_authenticated,
    reject_unauth_destination,
    reject_invalid_hostname,
    reject_unknown_recipient_domain,
    reject_rbl_client zen.spamhaus.org,
    reject_rbl_client bl.spamcop.net
```

## Vulnerability Management

### Image Scanning
```bash
# Trivy security scanning
trivy image podplay-apache-debian:latest

# Clair scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    quay.io/coreos/clair-local-scan podplay-apache-debian:latest
```

### Dependency Scanning
```bash
# Python dependency scanning
safety check -r requirements.txt

# Node.js dependency scanning
npm audit
```

### Base Image Updates
```dockerfile
# Pin base image versions with digest
FROM debian:bookworm-slim@sha256:abc123...

# Update strategy
ARG DEBIAN_VERSION=bookworm-20240101
FROM debian:${DEBIAN_VERSION}-slim
```

## Monitoring and Logging

### Security Event Logging
```bash
# Audit logging configuration
audit.log {
    "timestamp": "2024-01-20T10:30:00Z",
    "event": "authentication_failure",
    "source_ip": "192.168.1.100",
    "user": "admin",
    "service": "apache",
    "severity": "high"
}
```

### Failed Authentication Monitoring
```bash
# Monitor failed login attempts
fail2ban-client status apache-auth
fail2ban-client status ssh
```

### Certificate Expiry Monitoring
```python
#!/usr/bin/env python3
import ssl
import socket
from datetime import datetime, timedelta

def check_certificate_expiry(hostname, port=443):
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_until_expiry = (expiry - datetime.now()).days
            return days_until_expiry

# Alert if certificate expires within 30 days
if check_certificate_expiry('example.com') < 30:
    send_alert("Certificate expiring soon")
```

## Incident Response

### Security Incident Playbook
```bash
# 1. Isolate affected containers
podman stop affected-container
podman network disconnect affected-container from all-networks

# 2. Preserve evidence
podman commit affected-container evidence-image
podman export affected-container > /evidence/container-export.tar

# 3. Analyze logs
podman logs affected-container > /evidence/container.log
journalctl -u container-service > /evidence/system.log

# 4. Check for compromise indicators
podman exec affected-container find / -type f -mtime -1 2>/dev/null
podman exec affected-container netstat -tlnp
```

### Backup and Recovery
```bash
# Secure backup script
#!/bin/bash
set -e

BACKUP_DIR="/secure/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup certificates
tar -czf "$BACKUP_DIR/certificates.tar.gz" /data/certificates/

# Backup configurations
tar -czf "$BACKUP_DIR/configs.tar.gz" /etc/

# Encrypt backups
gpg --cipher-algo AES256 --compress-algo 1 --symmetric \
    --output "$BACKUP_DIR/certificates.tar.gz.gpg" \
    "$BACKUP_DIR/certificates.tar.gz"

# Remove unencrypted backups
rm "$BACKUP_DIR"/*.tar.gz

# Verify backup integrity
gpg --decrypt "$BACKUP_DIR/certificates.tar.gz.gpg" | tar -tz > /dev/null
```

## Compliance Requirements

### PCI DSS Considerations
- Encrypt cardholder data in transit and at rest
- Implement strong access control measures
- Regular vulnerability assessments
- Secure network architecture

### GDPR Considerations
- Data protection by design and default
- Encryption of personal data
- Audit trails for data access
- Right to erasure implementation

### SOC 2 Controls
- Access controls and authentication
- System monitoring and logging
- Change management procedures
- Incident response processes

## Security Testing

### Penetration Testing
```bash
# Network vulnerability scanning
nmap -sS -O target-host

# Web application scanning
nikto -h https://target-host
owasp-zap-baseline.py -t https://target-host

# SSL/TLS testing
testssl.sh target-host:443
```

### Security Validation
```bash
# Container security benchmark
docker-bench-security.sh

# Host security hardening
lynis audit system
```

## Future Security Enhancements

1. **Zero Trust Architecture**
   - mTLS for all service communication
   - Identity-based access controls
   - Continuous verification

2. **Advanced Threat Detection**
   - Behavioral analysis
   - Machine learning anomaly detection
   - Real-time threat intelligence

3. **Security Automation**
   - Automated vulnerability patching
   - Security orchestration (SOAR)
   - Compliance automation