#!/bin/bash
set -e

# Validate required environment variables
validate_environment() {
    local missing_vars=()
    
    if [ -z "$MAIL_SERVER_NAME" ]; then
        missing_vars+=("MAIL_SERVER_NAME")
    fi
    
    if [ -z "$MAIL_DOMAIN" ]; then
        missing_vars+=("MAIL_DOMAIN")
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "[$(date -Iseconds)] [ERROR] [MAIL] [INIT]: Required environment variables not set: ${missing_vars[*]}"
        echo "[$(date -Iseconds)] [ERROR] [MAIL] [INIT]: Mail container requires MAIL_SERVER_NAME and MAIL_DOMAIN to be explicitly set"
        echo "[$(date -Iseconds)] [ERROR] [MAIL] [INIT]: Exiting due to missing configuration"
        exit 1
    fi
}

# Call validation first
validate_environment

# Set SSL certificate paths based on validated domain
export SSL_CERT_FILE=${SSL_CERT_FILE:-"/data/certificates/$MAIL_DOMAIN/fullchain.pem"}
export SSL_KEY_FILE=${SSL_KEY_FILE:-"/data/certificates/$MAIL_DOMAIN/privkey.pem"}
export SSL_CHAIN_FILE=${SSL_CHAIN_FILE:-"/data/certificates/$MAIL_DOMAIN/fullchain.pem"}

# Setup logging infrastructure
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Initializing mail dual logging..."
    
    # Ensure log files exist with proper permissions
    touch /data/logs/mail/{postfix,dovecot,dovecot-info,auth,supervisord,health-monitor,opendkim}.log
    touch /data/logs/mail/{postfix-error,dovecot-error,cert-reload,cert-reload-error,user-reload,user-reload-error,health-monitor-error,opendkim-error}.log
    chown postfix:loggroup /data/logs/mail/postfix*.log
    chown dovecot:loggroup /data/logs/mail/dovecot*.log /data/logs/mail/auth.log
    chown opendkim:loggroup /data/logs/mail/opendkim*.log
    chown root:loggroup /data/logs/mail/{supervisord,health-monitor,cert-reload,user-reload}*.log
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

# Setup DKIM key generation and configuration
setup_dkim() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: Setting up DKIM authentication..."
    
    # Create DKIM key directory in persistent user-data volume (writable)
    DKIM_DIR="/data/user-data/dkim/${MAIL_DOMAIN}"
    mkdir -p "${DKIM_DIR}"
    
    # Generate DKIM keys if they don't exist
    if [ ! -f "${DKIM_DIR}/default.private" ]; then
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: Generating DKIM keys for ${MAIL_DOMAIN}..."
        
        # Generate key pair in persistent storage
        opendkim-genkey -t -s default -d "${MAIL_DOMAIN}" -D "${DKIM_DIR}/"
        
        # Set proper ownership
        chown -R opendkim:certgroup "${DKIM_DIR}"
        chmod 400 "${DKIM_DIR}/default.private"
        chmod 444 "${DKIM_DIR}/default.txt"
        
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: DKIM keys generated successfully in persistent storage"
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: Public key record:"
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: ====================="
        cat "${DKIM_DIR}/default.txt"
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: ====================="
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: Add this TXT record to your DNS:"
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: Name: default._domainkey.${MAIL_DOMAIN}"
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: Keys stored in: ${DKIM_DIR}"
    else
        echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: DKIM keys already exist in persistent storage, skipping generation"
        # Ensure proper ownership of existing keys
        chown -R opendkim:certgroup "${DKIM_DIR}"
        chmod 400 "${DKIM_DIR}/default.private"
        chmod 444 "${DKIM_DIR}/default.txt"
    fi
    
    # Ensure OpenDKIM directories and permissions
    mkdir -p /var/run/opendkim
    chown opendkim:opendkim /var/run/opendkim
    
    # Create log file for OpenDKIM  
    touch /data/logs/mail/opendkim.log
    chown opendkim:loggroup /data/logs/mail/opendkim.log
    chmod 644 /data/logs/mail/opendkim.log
    
    echo "[$(date -Iseconds)] [INFO] [MAIL] [DKIM]: DKIM setup complete"
}

# Call DKIM setup
setup_dkim

# Process Postfix configuration template
envsubst '${MAIL_SERVER_NAME} ${MAIL_DOMAIN} ${SSL_CERT_FILE} ${SSL_KEY_FILE} ${SSL_CHAIN_FILE}' \
    < /etc/postfix/main.cf.template > /etc/postfix/main.cf

# Setup user management infrastructure
setup_user_management() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Setting up user data structure..."
    
    # Create user-data directory structure
    mkdir -p /data/user-data/{config,users,shared/{public,templates,admin/{user-backups,migration-tools}}}
    
    # Create default user configuration if none exists
    if [ ! -f /data/user-data/config/users.yaml ]; then
        echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Creating initial user configuration with hashed passwords..."
        
        # Create minimal initial structure
        cat > /data/user-data/config/users.yaml << EOF
version: "1.0"
domains: []
test_users: []
EOF
        
        # Set ownership for Apache container access
        chown 33:33 /data/user-data/config/users.yaml
        chmod 664 /data/user-data/config/users.yaml
        
        # Use user_manager.py to properly add admin user with hashed password
        echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Adding default admin user with hashed password..."
        /data/.venv/bin/python /data/src/user_manager.py \
            --add-user \
            --user "admin" \
            --password "changeme123" \
            --domain "${MAIL_DOMAIN}" \
            --quota "1G" \
            --services "mail,www,files" \
            >> /data/logs/mail/user-reload.log 2>&1
        
        if [ $? -eq 0 ]; then
            echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Default admin user created successfully with hashed password"
        else
            echo "[$(date -Iseconds)] [ERROR] [MAIL] [INIT]: Failed to create default admin user"
        fi
        
        # Add default test user
        /data/.venv/bin/python /data/src/user_manager.py \
            --add-user \
            --user "test1" \
            --password "password1" \
            --domain "${MAIL_DOMAIN}" \
            --quota "50M" \
            --services "mail" \
            >> /data/logs/mail/user-reload.log 2>&1
        
        if [ $? -eq 0 ]; then
            echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Default test user created successfully with hashed password"
        else
            echo "[$(date -Iseconds)] [ERROR] [MAIL] [INIT]: Failed to create default test user"
        fi
    fi
    
    # Set proper ownership and permissions for cross-container access
    chown -R vmail:vmail /data/user-data/users
    chmod 775 /data/user-data/config
    
    # Set specific permissions for user configuration files
    if [ -f /data/user-data/config/users.yaml ]; then
        chown 33:33 /data/user-data/config/users.yaml
        chmod 664 /data/user-data/config/users.yaml
    fi
    
    echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: User data structure initialized"
}

# Call user management setup
setup_user_management

# Generate initial service configuration files
echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Generating initial service configuration files..."
/data/.venv/bin/python /data/src/user_manager.py --generate-initial --service-type mail
echo "[$(date -Iseconds)] [INFO] [MAIL] [USER-MANAGER]: Initial configuration files generated"

echo ""
echo "Mail server configuration complete!"
echo "  - SMTP: port 25 (plain), 587 (TLS)"
echo "  - IMAP: port 143 (plain), 993 (TLS)"
echo "  - POP3: port 110 (plain), 995 (TLS)"
echo "  - User management: Dynamic configuration from /data/user-data/config/users.yaml"
echo "  - Default users: admin@$MAIL_DOMAIN, test1@$MAIL_DOMAIN"
echo ""

# Final system status verification
final_system_check() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Starting supervisord to manage mail services..."
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: All services will be monitored and auto-restarted by supervisord"
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Check service status with: supervisorctl status"
    echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: View service logs in: /data/logs/mail/"
}

# Run final verification
final_system_check

# Set up signal traps for graceful shutdown
trap_signals() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [SHUTDOWN]: Received shutdown signal, stopping supervisord..."
    supervisorctl shutdown
    echo "[$(date -Iseconds)] [INFO] [MAIL] [SHUTDOWN]: Mail container shutdown complete"
    exit 0
}

# Set up signal traps
trap trap_signals SIGTERM SIGINT

# Start supervisord (this will manage all our services)
echo "[$(date -Iseconds)] [INFO] [MAIL] [INIT]: Starting supervisord with mail service management..."
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf