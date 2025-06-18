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
cat > /etc/apache2/conf.d/ssl.conf << EOF
LoadModule ssl_module modules/mod_ssl.so
LoadModule socache_shmcb_module modules/mod_socache_shmcb.so

Listen 443

<VirtualHost *:443>
    ServerName ${FQDN}
    DocumentRoot /var/www/localhost/htdocs
    
    SSLEngine on
    SSLCertificateFile ${CERT_DIR}/fullchain.pem
    SSLCertificateKeyFile ${CERT_DIR}/privkey.pem
    
    # Modern SSL configuration
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384
    SSLHonorCipherOrder on
    
    <Directory /var/www/localhost/htdocs>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # Add a header to indicate HTTPS
    Header always set X-Protocol "HTTPS"
</VirtualHost>
EOF

# Create HTTP configuration
cat > /etc/apache2/conf.d/http.conf << EOF
LoadModule headers_module modules/mod_headers.so

<VirtualHost *:80>
    ServerName ${FQDN}
    DocumentRoot /var/www/localhost/htdocs
    
    <Directory /var/www/localhost/htdocs>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # Add a header to indicate HTTP
    Header always set X-Protocol "HTTP"
</VirtualHost>
EOF

# Remove default.conf which might be interfering
rm -f /etc/apache2/conf.d/default.conf

# Create simple test page for debugging
echo "It works!" > /var/www/localhost/htdocs/test.txt

# Create a simple index page
mkdir -p /var/www/localhost/htdocs
cat > /var/www/localhost/htdocs/index.html << EOF
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
chown -R apache:apache /var/www/localhost/htdocs

# Set global ServerName to suppress warning
echo "ServerName $FQDN" >> /etc/apache2/httpd.conf

# Start Apache in foreground
echo "Starting Apache..."
exec httpd -D FOREGROUND