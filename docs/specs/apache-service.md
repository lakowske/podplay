# Apache Web Server Service Specification

## Purpose
Define the requirements and implementation details for the Apache HTTP server container service.

## Scope
- Apache HTTP Server configuration
- SSL/TLS implementation
- Virtual host management
- Performance optimization
- Security hardening

## Requirements

### Functional Requirements
1. Serve HTTP and HTTPS traffic
2. Support multiple virtual hosts
3. Automatic SSL/TLS configuration
4. Custom error pages
5. Access logging and metrics

### Non-Functional Requirements
1. Modern TLS protocols (1.2+)
2. Strong cipher suites
3. HTTP/2 support
4. Efficient static file serving
5. < 100MB container image size

## Design Decisions

### Base Configuration
```apache
# Core modules
LoadModule ssl_module modules/mod_ssl.so
LoadModule headers_module modules/mod_headers.so
LoadModule rewrite_module modules/mod_rewrite.so
LoadModule http2_module modules/mod_http2.so

# Security headers
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "DENY"
Header always set X-XSS-Protection "1; mode=block"
Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
```

### SSL/TLS Configuration
```apache
# Modern SSL configuration
SSLProtocol -all +TLSv1.2 +TLSv1.3
SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384
SSLHonorCipherOrder on
SSLSessionTickets off

# OCSP Stapling
SSLUseStapling on
SSLStaplingCache "shmcb:logs/ssl_stapling(32768)"
```

## Implementation

### Dockerfile Structure
```dockerfile
FROM base-debian:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/*

# Enable required modules
RUN a2enmod ssl headers rewrite http2

# Add www-data to certgroup
RUN usermod -a -G certgroup www-data

# Copy configuration templates
COPY configs/ /etc/apache2/templates/
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

EXPOSE 80 443

ENTRYPOINT ["/entrypoint.sh"]
```

### Virtual Host Template
```apache
<VirtualHost *:80>
    ServerName ${DOMAIN}
    DocumentRoot /var/www/html

    # Redirect HTTP to HTTPS
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}$1 [R=301,L]
</VirtualHost>

<VirtualHost *:443>
    ServerName ${DOMAIN}
    DocumentRoot /var/www/html

    # SSL Configuration
    SSLEngine on
    SSLCertificateFile ${CERT_PATH}/fullchain.pem
    SSLCertificateKeyFile ${CERT_PATH}/privkey.pem

    # HTTP/2
    Protocols h2 http/1.1

    # Document root
    <Directory /var/www/html>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    # Logging
    ErrorLog ${APACHE_LOG_DIR}/${DOMAIN}-error.log
    CustomLog ${APACHE_LOG_DIR}/${DOMAIN}-access.log combined
</VirtualHost>
```

### Entrypoint Script
```bash
#!/bin/bash
set -e

# Wait for certificates
wait_for_certificates() {
    echo "Waiting for SSL certificates..."
    while [ ! -f "/data/certificates/${DOMAIN}/fullchain.pem" ]; do
        echo "Certificates not found. Retrying in 5 seconds..."
        sleep 5
    done
    echo "Certificates found!"
}

# Generate configuration
generate_config() {
    echo "Generating Apache configuration for ${DOMAIN}..."
    export CERT_PATH="/data/certificates/${DOMAIN}"
    envsubst < /etc/apache2/templates/vhost.template > /etc/apache2/sites-available/${DOMAIN}.conf
    a2ensite ${DOMAIN}
    a2dissite 000-default
}

# Validate configuration
validate_config() {
    echo "Testing Apache configuration..."
    apache2ctl configtest
}

# Start Apache
start_apache() {
    echo "Starting Apache..."
    # Run in foreground
    exec apache2ctl -D FOREGROUND
}

# Main execution
wait_for_certificates
generate_config
validate_config
start_apache
```

## Performance Optimization

### Compression
```apache
# Enable compression
LoadModule deflate_module modules/mod_deflate.so
AddOutputFilterByType DEFLATE text/html text/plain text/xml text/css text/javascript application/javascript
```

### Caching Headers
```apache
# Static asset caching
<FilesMatch "\.(jpg|jpeg|png|gif|ico|css|js)$">
    Header set Cache-Control "max-age=31536000, public"
</FilesMatch>
```

### Connection Tuning
```apache
# Keep-alive settings
KeepAlive On
MaxKeepAliveRequests 100
KeepAliveTimeout 5

# Worker MPM settings
<IfModule mpm_worker_module>
    StartServers 2
    MinSpareThreads 25
    MaxSpareThreads 75
    ThreadLimit 64
    ThreadsPerChild 25
    MaxRequestWorkers 150
    MaxConnectionsPerChild 0
</IfModule>
```

## Security Configuration

### Directory Permissions
```apache
# Disable directory listing
Options -Indexes

# Prevent access to hidden files
<FilesMatch "^\.">
    Require all denied
</FilesMatch>

# Protect sensitive files
<FilesMatch "(^\.env|\.git|composer\.(json|lock))">
    Require all denied
</FilesMatch>
```

### Request Limits
```apache
# Limit request size
LimitRequestBody 10485760  # 10MB

# Timeout settings
Timeout 60
```

## Monitoring

### Health Check Endpoint
```apache
# Health check location
<Location /health>
    SetHandler server-status
    Require local
</Location>
```

### Access Logging
```apache
# Custom log format with response time
LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %D" combined_time
CustomLog ${APACHE_LOG_DIR}/access.log combined_time
```

## Testing Procedures

### Configuration Tests
```bash
# Syntax check
apache2ctl -t

# Module verification
apache2ctl -M

# SSL/TLS testing
openssl s_client -connect localhost:443 -tls1_2
```

### Performance Tests
```bash
# Load testing
ab -n 1000 -c 10 https://localhost/

# SSL performance
openssl speed rsa2048
```

## Container Integration

### Running the Container
```bash
podman run -d \
    --name apache \
    -p 8080:80 \
    -p 8443:443 \
    -v certs:/data/certificates:ro \
    -v apache-logs:/var/log/apache2 \
    -e DOMAIN=example.com \
    podplay-apache-debian:latest
```

### Volume Mounts
- `/data/certificates`: SSL certificates (read-only)
- `/var/www/html`: Web content
- `/var/log/apache2`: Log files

## Future Enhancements

1. **Advanced Features**
   - ModSecurity WAF integration
   - Brotli compression
   - HTTP/3 support
   - WebSocket proxying

2. **Scaling**
   - Load balancer integration
   - Session clustering
   - CDN integration

3. **Automation**
   - Auto-discovery of virtual hosts
   - Dynamic certificate loading
   - Automated performance tuning