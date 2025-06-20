# Certificate Management Specification

## Purpose
Define the unified certificate management system for secure communication across all services.

## Scope
- Certificate storage and access patterns
- Permission model for multi-service access
- Dynamic certificate detection and monitoring
- Certificate lifecycle management

## Requirements

### Functional Requirements
1. Support multiple certificate types (self-signed, Let's Encrypt)
2. Enable shared read access for all services
3. Maintain secure write access for certificate generation
4. Provide real-time certificate change detection
5. Support multiple domains

### Non-Functional Requirements
1. Secure storage with appropriate file permissions
2. Zero-downtime certificate updates
3. Automatic service reconfiguration on certificate changes
4. Audit trail for certificate operations

## Design Decisions

### Storage Structure
```
/data/certificates/
├── domain.txt                    # Current active domain
├── lab.sethlakowske.com/         # Domain-specific directory
│   ├── fullchain.pem            # Certificate chain (644)
│   ├── privkey.pem              # Private key (640)
│   ├── cert.pem                 # Certificate only
│   └── chain.pem                # Intermediate chain
└── example.com/                  # Additional domain
    ├── fullchain.pem
    └── privkey.pem
```

### Permission Model
```bash
# Certificate files
-rw-r--r-- 1 certuser certgroup  fullchain.pem (644)
-rw-r----- 1 certuser certgroup  privkey.pem   (640)

# Service access
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
         groups=33(www-data),9999(certgroup)
```

### User/Group Architecture
- **certuser** (UID 9999): Owns all certificates
- **certgroup** (GID 9999): Shared group for access
- **Service users**: Added to certgroup during container build

## Implementation Guidelines

### Certificate Discovery
```python
def find_certificates(path):
    """Find all certificate files in the given path."""
    cert_extensions = {'.pem', '.crt', '.cer', '.key'}
    # Recursive search implementation
```

### Dynamic Monitoring
```python
# Using watchdog for efficient file system monitoring
class CertificateEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Handle new certificate
    def on_modified(self, event):
        # Handle certificate update
    def on_deleted(self, event):
        # Handle certificate removal
```

### Service Integration Pattern
```bash
#!/bin/bash
# Service entrypoint.sh

# Wait for certificates
echo "Waiting for SSL certificates..."
while [ ! -f "/data/certificates/${DOMAIN}/fullchain.pem" ]; do
    echo "Certificates not found. Retrying in 5 seconds..."
    sleep 5
done

# Configure service with certificates
configure_ssl() {
    local cert_path="/data/certificates/${DOMAIN}"
    # Service-specific SSL configuration
}
```

## Certificate Types

### Self-Signed Certificates
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout privkey.pem \
    -out fullchain.pem \
    -subj "/CN=${DOMAIN}"
```

### Let's Encrypt Certificates
```bash
certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email ${EMAIL} \
    --domains ${DOMAIN} \
    --cert-path /data/certificates/${DOMAIN}
```

## Volume Management

### Creation
```bash
podman volume create certs
```

### Mounting Patterns
```bash
# Read-write for certificate generation
-v certs:/data/certificates

# Read-only for services
-v certs:/data/certificates:ro
```

## Security Considerations

### File Permissions
- Public certificates: 644 (readable by all)
- Private keys: 640 (readable by owner and group only)
- Directory: 755 (traversable by all, writable by owner)

### Access Control
- Services run as non-root users
- Write access restricted to certbot container
- No direct host filesystem mounting

### Key Rotation
- Support for zero-downtime rotation
- Automatic detection of new certificates
- Service reload without restart

## Monitoring and Alerting

### Certificate Expiry
```python
def check_certificate_expiry(cert_path):
    """Check days until certificate expiration."""
    # Implementation for expiry monitoring
```

### Event Notifications
- Certificate creation
- Certificate renewal
- Certificate expiration warnings
- Access permission errors

## Testing Considerations

1. **Permission Tests**
   - Verify correct ownership and permissions
   - Test group access for different services
   - Validate read-only mount enforcement

2. **Integration Tests**
   - Certificate detection by services
   - Service startup with missing certificates
   - Certificate rotation handling

3. **Security Tests**
   - Attempt unauthorized certificate access
   - Verify private key protection
   - Test certificate validation

## Error Handling

### Missing Certificates
- Services should wait and retry
- Clear error messages
- Configurable timeout periods

### Permission Errors
- Diagnostic logging
- Suggested remediation steps
- Fallback to non-SSL if configured

## Future Enhancements

1. **Certificate Management API**
   - RESTful API for certificate operations
   - Web UI for certificate status
   - Automated renewal scheduling

2. **Multi-Domain Support**
   - Wildcard certificates
   - Subject Alternative Names (SAN)
   - Per-service certificate selection

3. **Integration Features**
   - ACME DNS challenge support
   - Hardware Security Module (HSM) integration
   - Certificate transparency logging