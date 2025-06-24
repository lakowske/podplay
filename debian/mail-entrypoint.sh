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

# Setup user management infrastructure
setup_user_management() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Setting up user data structure..."
    
    # Create user-data directory structure
    mkdir -p /data/user-data/{config,users,shared/{public,templates,admin/{user-backups,migration-tools}}}
    
    # IMPORTANT: Cross-container permissions strategy
    # The Apache container (www-data, UID 33) needs write access to users.yaml for registration
    # The Mail container creates these files but must set ownership for Apache access
    
    # Create default user configuration if none exists
    if [ ! -f /data/user-data/config/users.yaml ]; then
        cat > /data/user-data/config/users.yaml << EOF
version: "1.0"
domains:
  - name: "${MAIL_DOMAIN}"
    users:
      - username: "admin"
        password: "password"
        aliases: ["postmaster", "hostmaster", "root"]
        quota: "1G"
        enabled: true
        services: ["mail"]
test_users:
  - username: "test1"
    password: "password1"
    domain: "${MAIL_DOMAIN}"
    quota: "50M"
    services: ["mail"]
EOF
        # Set ownership immediately after creation for Apache container access
        chown 33:33 /data/user-data/config/users.yaml
        chmod 664 /data/user-data/config/users.yaml
    fi
    
    # Create default quota configuration
    if [ ! -f /data/user-data/config/quotas.yaml ]; then
        cat > /data/user-data/config/quotas.yaml << EOF
default_quotas:
  test_users: "50M"
  regular_users: "500M"
  admin_users: "2G"

service_quotas:
  mail: "50%"
  files: "30%"
  git: "15%"
  www: "5%"

monitoring:
  warning_threshold: 80
  critical_threshold: 95
  cleanup_threshold: 98
EOF
        # Set ownership immediately after creation
        chown 33:33 /data/user-data/config/quotas.yaml
        chmod 664 /data/user-data/config/quotas.yaml
    fi
    
    # Set proper ownership and permissions for cross-container access
    chown -R vmail:vmail /data/user-data/users
    
    # Set permissions for config files to allow Apache container (www-data) to modify them
    # The Apache and Mail containers share the user-data volume, so we need shared access
    chmod 775 /data/user-data/config
    
    # Set specific permissions for user configuration files
    if [ -f /data/user-data/config/users.yaml ]; then
        # Allow www-data (UID 33) from Apache container to read/write
        chown 33:33 /data/user-data/config/users.yaml
        chmod 664 /data/user-data/config/users.yaml
    fi
    
    if [ -f /data/user-data/config/quotas.yaml ]; then
        chown 33:33 /data/user-data/config/quotas.yaml  
        chmod 664 /data/user-data/config/quotas.yaml
    fi
    
    echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: User data structure initialized"
}

# Start user management daemon
start_user_manager() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Starting user configuration hot-reload monitor..."
    
    # Start user manager in background
    /data/.venv/bin/python /data/src/user_manager.py \
        --hot-reload \
        --watch /data/user-data/config/ \
        --service-type mail \
        --domain "$MAIL_DOMAIN" \
        >> /data/logs/mail/user-reload.log 2>&1 &
    
    USER_MANAGER_PID=$!
    echo $USER_MANAGER_PID > /tmp/user-manager.pid
    echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Monitor started (PID: $USER_MANAGER_PID)"
}

# Initialize user management
setup_user_management

# Generate initial user configuration files
echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Generating initial service configuration files..."

# Use debug logging if requested
if [ "${PODPLAY_LOG_LEVEL}" = "DEBUG" ] || [ "${PODPLAY_MAIL_LOG_LEVEL}" = "DEBUG" ]; then
    export PODPLAY_USER_LOG_LEVEL=DEBUG
fi

# Generate initial configurations
/data/.venv/bin/python /data/src/user_manager.py \
    --generate-initial \
    --watch /data/user-data/config/users.yaml \
    --service-type mail \
    --domain "$MAIL_DOMAIN" \
    2>&1 | tee /tmp/user-config-init.log

# Verify configuration files were created
if [ ! -f /etc/postfix/vmailbox ] || [ ! -f /etc/dovecot/passwd ]; then
    echo "[$(date -Iseconds)] [ERROR] [MAIL] [USER-MANAGER]: Failed to generate initial configuration files"
    exit 1
fi

echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Initial configuration files generated"

echo ""
echo "Mail server configuration complete!"
echo "  - SMTP: port 25 (plain), 587 (TLS)"
echo "  - IMAP: port 143 (plain), 993 (TLS)"
echo "  - POP3: port 110 (plain), 995 (TLS)"
echo "  - User management: Dynamic configuration from /data/user-data/config/users.yaml"
echo "  - Default users: admin@$MAIL_DOMAIN, test1@$MAIL_DOMAIN"
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

# Start certificate monitoring daemon
start_certificate_monitor() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [CERT-MONITOR]: Starting certificate hot-reload monitor..."
    
    # Start certificate monitor in background
    /data/src/cert_manager.py \
        --hot-reload \
        --service-type mail \
        --domain "$MAIL_DOMAIN" \
        /data/certificates/ \
        >> /data/logs/mail/cert-reload.log 2>&1 &
    
    CERT_MONITOR_PID=$!
    echo $CERT_MONITOR_PID > /tmp/cert-monitor.pid
    echo "[$(date -Iseconds)] [INFO] [MAIL] [CERT-MONITOR]: Monitor started (PID: $CERT_MONITOR_PID)"
}

# Start certificate monitor
start_certificate_monitor

# Start user manager
start_user_manager

# Keep container running and show logs
echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Mail services started successfully with certificate and user hot-reload!"
tail_mail_logs

# Keep the container running
tail -f /dev/null