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
    
    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # Add a header to indicate HTTPS
    Header always set X-Protocol "HTTPS"
</VirtualHost>
EOF

# Update HTTP configuration
cat > /etc/apache2/sites-available/000-default.conf << EOF
<VirtualHost *:80>
    ServerName ${FQDN}
    DocumentRoot /var/www/html
    
    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # Add a header to indicate HTTP
    Header always set X-Protocol "HTTP"
</VirtualHost>
EOF

# Enable sites
a2ensite 000-default-ssl

# Create simple test page for debugging
echo "It works!" > /var/www/html/test.txt

# Create a simple index page
cat > /var/www/html/index.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Apache with SSL</title>
</head>
<body>
    <h1>Apache is running with SSL!</h1>
    <p>This page is served over HTTPS using certificates from the shared volume.</p>
</body>
</html>
EOF

# Fix permissions
chown -R www-data:www-data /var/www/html

# Set global ServerName to suppress warning
echo "ServerName $FQDN" >> /etc/apache2/apache2.conf

# Remove Apache PID file if it exists
rm -f /var/run/apache2/apache2.pid

# Start Apache in foreground
echo "Starting Apache..."
exec apache2ctl -D FOREGROUND