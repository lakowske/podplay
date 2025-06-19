#!/bin/bash
set -e

# Set default environment variables
export MAIL_SERVER_NAME=${MAIL_SERVER_NAME:-"lab.sethlakowske.com"}
export MAIL_DOMAIN=${MAIL_DOMAIN:-"lab.sethlakowske.com"}
export SSL_CERT_FILE=${SSL_CERT_FILE:-"/data/certificates/$MAIL_DOMAIN/fullchain.pem"}
export SSL_KEY_FILE=${SSL_KEY_FILE:-"/data/certificates/$MAIL_DOMAIN/privkey.pem"}
export SSL_CHAIN_FILE=${SSL_CHAIN_FILE:-"/data/certificates/$MAIL_DOMAIN/fullchain.pem"}

echo "Starting mail server for domain: $MAIL_DOMAIN"
echo "Server name: $MAIL_SERVER_NAME"

# Set up directory permissions following Alpine conventions
chown vmail:postdrop /var/spool/mail/vhosts
chmod 755 /var/spool/mail/vhosts
chown root:dovecot /etc/ssl/certs/dovecot
chmod 755 /etc/ssl/certs/dovecot

# Check for SSL certificates and copy them
SSL_ENABLED="false"
if [ -f "$SSL_CERT_FILE" ] && [ -f "$SSL_KEY_FILE" ]; then
    SSL_ENABLED="true"
    echo "SSL certificates found, enabling TLS"
    
    # Copy certificates to Alpine Dovecot location
    cp "$SSL_CERT_FILE" /etc/ssl/dovecot/server.pem
    cp "$SSL_KEY_FILE" /etc/ssl/dovecot/server.key
    
    # Set proper permissions using usernames
    chown root:dovecot /etc/ssl/dovecot/server.key
    chmod 640 /etc/ssl/dovecot/server.key
    chmod 644 /etc/ssl/dovecot/server.pem
    
    # Update SSL file paths for templates
    export SSL_CERT_FILE="/etc/ssl/certs/dovecot/fullchain.pem"
    export SSL_KEY_FILE="/etc/ssl/certs/dovecot/privkey.pem"
    export SSL_CHAIN_FILE="/etc/ssl/certs/dovecot/fullchain.pem"
    
    echo "Certificates configured for SSL/TLS"
else
    echo "Warning: SSL certificates not found, running without TLS"
fi

# Process Postfix configuration template
envsubst '${MAIL_SERVER_NAME} ${MAIL_DOMAIN} ${SSL_CERT_FILE} ${SSL_KEY_FILE} ${SSL_CHAIN_FILE}' \
    < /etc/postfix/main.cf.template > /etc/postfix/main.cf

# Create admin user mailbox directory following Alpine structure
echo "Creating admin user: admin@$MAIL_DOMAIN"
mkdir -p "/var/spool/mail/vhosts/$MAIL_DOMAIN/admin"
chown -R vmail:postdrop "/var/spool/mail/vhosts/$MAIL_DOMAIN"

# Create Postfix virtual maps following Alpine Linux format
echo "admin@$MAIL_DOMAIN    $MAIL_DOMAIN/admin/" > /etc/postfix/vmailbox
postmap /etc/postfix/vmailbox

# Create virtual aliases file
echo "postmaster@$MAIL_DOMAIN    admin@$MAIL_DOMAIN" > /etc/postfix/valias
echo "hostmaster@$MAIL_DOMAIN    admin@$MAIL_DOMAIN" > /etc/postfix/valias
postmap /etc/postfix/valias

# Create standard aliases
echo "postmaster: admin@$MAIL_DOMAIN" > /etc/postfix/aliases
echo "root: admin@$MAIL_DOMAIN" >> /etc/postfix/aliases
postalias /etc/postfix/aliases

# Note: Using static authentication in dovecot.conf for simplicity

echo ""
echo "Mail server configuration complete!"
echo "  - SMTP: port 25 (plain), 587 (TLS)"
echo "  - IMAP: port 143 (plain), 993 (TLS)"
echo "  - POP3: port 110 (plain), 995 (TLS)"
echo "  - Admin account: admin@$MAIL_DOMAIN (password: password)"
echo ""

# Start Postfix
echo "Starting Postfix..."
postfix start

# Start Dovecot with Alpine configuration
echo "Starting Dovecot..."
dovecot

# Keep container running and show logs
echo "Mail services started successfully!"
tail -f /var/log/dovecot 2>/dev/null || tail -f /dev/null