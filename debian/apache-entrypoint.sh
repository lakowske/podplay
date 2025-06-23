#!/bin/bash

# Certificate base directory
CERT_BASE="/data/certificates"

# Get domain from environment or certificate info
if [ -n "$DOMAIN" ]; then
    FQDN="$DOMAIN"
elif [ -f "$CERT_BASE/domain.txt" ]; then
    FQDN=$(cat "$CERT_BASE/domain.txt")
else
    FQDN="localhost"
fi

echo "Using domain: $FQDN"

# Certificate directory
CERT_DIR="$CERT_BASE/$FQDN"

# Setup logging infrastructure
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [APACHE] [INIT]: Initializing dual logging..."
    
    # Ensure log files exist with proper permissions
    touch /data/logs/apache/{access,error,ssl}.log
    chown www-data:loggroup /data/logs/apache/*.log
    chmod 644 /data/logs/apache/*.log
    
    echo "[$(date -Iseconds)] [INFO] [APACHE] [INIT]: Logging initialized"
}

# Setup authentication infrastructure
setup_authentication() {
    echo "[$(date -Iseconds)] [INFO] [APACHE] [AUTH]: Initializing authentication system..."
    
    # Create authentication data directories with proper permissions
    mkdir -p /data/user-data/pending/{registrations,resets,sessions,rate_limits}
    chown -R www-data:www-data /data/user-data/pending
    
    # Create authentication log file
    touch /data/logs/apache/auth.log
    chown www-data:loggroup /data/logs/apache/auth.log
    chmod 644 /data/logs/apache/auth.log
    
    # Ensure CGI scripts are executable and have proper paths
    find /var/www/cgi-bin -name "*.py" -exec chmod +x {} \;
    
    echo "[$(date -Iseconds)] [INFO] [APACHE] [AUTH]: Authentication system initialized"
}

# Call logging setup
setup_logging

# Call authentication setup  
setup_authentication

# Wait for certificates to be available
echo "Checking for certificates in $CERT_DIR..."
while [ ! -f "$CERT_DIR/fullchain.pem" ] || [ ! -f "$CERT_DIR/privkey.pem" ]; do
    echo "Waiting for certificates to be generated..."
    sleep 5
done
echo "Certificates found!"

# Enable SSL module and default SSL site
echo "Configuring Apache for SSL..."

# Create SSL configuration
cat > /etc/apache2/sites-available/000-default-ssl.conf << EOF
<VirtualHost *:443>
    ServerName ${FQDN}
    DocumentRoot /var/www/html
    
    SSLEngine on
    SSLCertificateFile ${CERT_DIR}/fullchain.pem
    SSLCertificateKeyFile ${CERT_DIR}/privkey.pem
    
    # Modern SSL configuration
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384
    SSLHonorCipherOrder on
    
    # Dual logging configuration
    LogFormat "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [INFO] [APACHE] [ACCESS]: %h %l %u \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %D" combined_structured
    LogFormat "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [INFO] [APACHE] [SSL]: %h %{SSL_PROTOCOL}x %{SSL_CIPHER}x \"%r\" %>s" ssl_structured
    
    CustomLog /data/logs/apache/access.log combined_structured
    CustomLog /data/logs/apache/ssl.log ssl_structured
    ErrorLog /data/logs/apache/error.log
    
    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # CGI configuration for authentication
    ScriptAlias /cgi-bin/ /var/www/cgi-bin/
    <Directory "/var/www/cgi-bin">
        Options +ExecCGI
        AddHandler cgi-script .py
        Require all granted
        
        # Pass environment variables to CGI scripts
        PassEnv DOMAIN
        SetEnv PYTHONPATH /data/.venv/lib/python3.11/site-packages
    </Directory>
    
    # Protected portal area
    <Directory "/var/www/html/portal">
        Options -Indexes
        
        # Check for valid session using mod_rewrite
        RewriteEngine On
        RewriteCond %{HTTP_COOKIE} !session_id=sess_[a-zA-Z0-9]{32}
        RewriteRule ^.*$ /auth/login.html?redirect=%{REQUEST_URI} [R,L]
    </Directory>
    
    # Security headers for auth pages
    <Directory "/var/www/html/auth">
        Header always set X-Frame-Options "DENY"
        Header always set X-Content-Type-Options "nosniff"
        Header always set X-XSS-Protection "1; mode=block"
    </Directory>
    
    # Add security headers
    Header always set X-Protocol "HTTPS"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
</VirtualHost>
EOF

# Update HTTP configuration
cat > /etc/apache2/sites-available/000-default.conf << EOF
<VirtualHost *:80>
    ServerName ${FQDN}
    DocumentRoot /var/www/html
    
    # Dual logging configuration
    LogFormat "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [INFO] [APACHE] [ACCESS]: %h %l %u \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %D" combined_structured
    
    CustomLog /data/logs/apache/access.log combined_structured
    ErrorLog /data/logs/apache/error.log
    
    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # CGI configuration for authentication
    ScriptAlias /cgi-bin/ /var/www/cgi-bin/
    <Directory "/var/www/cgi-bin">
        Options +ExecCGI
        AddHandler cgi-script .py
        Require all granted
        
        # Pass environment variables to CGI scripts
        PassEnv DOMAIN
        SetEnv PYTHONPATH /data/.venv/lib/python3.11/site-packages
    </Directory>
    
    # Add a header to indicate HTTP
    Header always set X-Protocol "HTTP"
</VirtualHost>
EOF

# Enable sites
a2ensite 000-default-ssl

# Create simple test page for debugging
echo "It works!" > /var/www/html/test.txt

# Create a simple index page with authentication links
cat > /var/www/html/index.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>PodPlay - ${FQDN}</title>
    <link rel="stylesheet" href="/static/css/auth.css">
</head>
<body>
    <div class="auth-container">
        <h1>Welcome to PodPlay</h1>
        <p>This page is served over HTTPS using certificates from Let's Encrypt.</p>
        
        <div class="auth-links">
            <a href="/auth/login.html" class="btn btn-primary">Login</a>
            <a href="/auth/register.html">Create Account</a>
        </div>
        
        <hr>
        <p><strong>Domain:</strong> ${FQDN}</p>
        <p><strong>Services:</strong> Apache with SSL, User Authentication, Mail Server</p>
    </div>
</body>
</html>
EOF

# Fix permissions
chown -R www-data:www-data /var/www/html

# Set global ServerName to suppress warning
echo "ServerName $FQDN" >> /etc/apache2/apache2.conf

# Configure global logging format
cat >> /etc/apache2/apache2.conf << EOF

# Global logging configuration
ErrorLogFormat "[%{%Y-%m-%dT%H:%M:%S}t.%{msec_frac}t%{%z}t] [ERROR] [APACHE] [ERROR]: [pid %P] [client %a] %M"
EOF

# Remove Apache PID file if it exists
rm -f /var/run/apache2/apache2.pid

# Start certificate monitoring daemon
start_certificate_monitor() {
    echo "[$(date -Iseconds)] [INFO] [APACHE] [CERT-MONITOR]: Starting certificate hot-reload monitor..."
    
    # Start certificate monitor in background
    /data/src/cert_manager.py \
        --hot-reload \
        --service-type apache \
        --domain "$FQDN" \
        /data/certificates/ \
        >> /data/logs/apache/cert-reload.log 2>&1 &
    
    CERT_MONITOR_PID=$!
    echo $CERT_MONITOR_PID > /tmp/cert-monitor.pid
    echo "[$(date -Iseconds)] [INFO] [APACHE] [CERT-MONITOR]: Monitor started (PID: $CERT_MONITOR_PID)"
}

# Start certificate monitor before Apache
start_certificate_monitor

# Start Apache in foreground
echo "[$(date -Iseconds)] [INFO] [APACHE] [INIT]: Starting Apache with dual logging and certificate hot-reload..."
exec apache2ctl -D FOREGROUND