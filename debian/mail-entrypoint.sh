#!/bin/bash
set -e

# Set default environment variables
export MAIL_SERVER_NAME=${MAIL_SERVER_NAME:-"lab.sethlakowske.com"}
export MAIL_DOMAIN=${MAIL_DOMAIN:-"lab.sethlakowske.com"}
export SSL_CERT_FILE=${SSL_CERT_FILE:-"/data/certificates/$MAIL_DOMAIN/fullchain.pem"}
export SSL_KEY_FILE=${SSL_KEY_FILE:-"/data/certificates/$MAIL_DOMAIN/privkey.pem"}
export SSL_CHAIN_FILE=${SSL_CHAIN_FILE:-"/data/certificates/$MAIL_DOMAIN/fullchain.pem"}

# Setup logging infrastructure
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Initializing mail dual logging..."
    
    # Ensure log files exist with proper permissions
    touch /data/logs/mail/{postfix,dovecot,dovecot-info,auth}.log
    chown postfix:loggroup /data/logs/mail/postfix.log
    chown dovecot:loggroup /data/logs/mail/dovecot*.log /data/logs/mail/auth.log
    chmod 644 /data/logs/mail/*.log
    
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Mail logging initialized"
}

# Call logging setup
setup_logging

echo "Starting mail server for domain: $MAIL_DOMAIN"
echo "Server name: $MAIL_SERVER_NAME"

# Set up directory permissions following Debian conventions
chown vmail:vmail /var/mail/vhosts
chmod 755 /var/mail/vhosts
chown root:dovecot /etc/ssl/certs/dovecot
chmod 755 /etc/ssl/certs/dovecot

# Check for SSL certificates and copy them
SSL_ENABLED="false"
if [ -f "$SSL_CERT_FILE" ] && [ -f "$SSL_KEY_FILE" ]; then
    SSL_ENABLED="true"
    echo "SSL certificates found, enabling TLS"
    
    # Copy certificates to both Dovecot and Postfix locations
    cp "$SSL_CERT_FILE" /etc/ssl/dovecot/server.pem
    cp "$SSL_KEY_FILE" /etc/ssl/dovecot/server.key
    cp "$SSL_CERT_FILE" /etc/ssl/certs/dovecot/fullchain.pem
    cp "$SSL_KEY_FILE" /etc/ssl/certs/dovecot/privkey.pem
    
    # Set proper permissions using usernames
    chown root:dovecot /etc/ssl/dovecot/server.key
    chmod 640 /etc/ssl/dovecot/server.key
    chmod 644 /etc/ssl/dovecot/server.pem
    
    # Set permissions for Postfix certificates
    chown root:postfix /etc/ssl/certs/dovecot/privkey.pem
    chmod 640 /etc/ssl/certs/dovecot/privkey.pem
    chmod 644 /etc/ssl/certs/dovecot/fullchain.pem
    
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

# Create admin user mailbox directory following Debian structure
echo "Creating admin user: admin@$MAIL_DOMAIN"
mkdir -p "/var/spool/mail/vhosts/$MAIL_DOMAIN/admin"
chown -R vmail:vmail "/var/spool/mail/vhosts/$MAIL_DOMAIN"

# Create Postfix virtual maps following Debian format
echo "admin@$MAIL_DOMAIN    $MAIL_DOMAIN/admin/" > /etc/postfix/vmailbox
postmap /etc/postfix/vmailbox

# Create virtual aliases file
echo "postmaster@$MAIL_DOMAIN    admin@$MAIL_DOMAIN" > /etc/postfix/valias
echo "hostmaster@$MAIL_DOMAIN    admin@$MAIL_DOMAIN" >> /etc/postfix/valias
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
service postfix start

# Start Dovecot with Debian configuration
echo "Starting Dovecot..."
service dovecot start

# Function to tail and redirect logs for dual logging
tail_mail_logs() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Starting dual logging for mail services..."
    
    # Tail Dovecot info logs (where LMTP activity is logged)
    if [ -f /var/log/dovecot-info.log ]; then
        tail -F /var/log/dovecot-info.log 2>/dev/null | while IFS= read -r line; do
            timestamp=$(date -Iseconds)
            structured_line="[$timestamp] [INFO] [MAIL] [DOVECOT]: $line"
            echo "$structured_line"
            echo "$structured_line" >> /data/logs/mail/dovecot-info.log
        done &
    fi
    
    # Tail Dovecot main logs
    if [ -f /var/log/dovecot.log ]; then
        tail -F /var/log/dovecot.log 2>/dev/null | while IFS= read -r line; do
            timestamp=$(date -Iseconds)
            structured_line="[$timestamp] [INFO] [MAIL] [DOVECOT]: $line"
            echo "$structured_line"
            echo "$structured_line" >> /data/logs/mail/dovecot.log
        done &
    fi
    
    # Monitor Postfix queue for activity
    while true; do
        sleep 5
        queue_status=$(postqueue -p 2>/dev/null)
        if [ "$queue_status" != "Mail queue is empty" ]; then
            timestamp=$(date -Iseconds)
            structured_line="[$timestamp] [INFO] [MAIL] [POSTFIX]: Queue activity detected"
            echo "$structured_line"
            echo "$structured_line" >> /data/logs/mail/postfix.log
        fi
    done &
}

# Keep container running and show logs
echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Mail services started successfully!"
tail_mail_logs

# Keep the container running
tail -f /dev/null