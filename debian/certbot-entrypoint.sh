#!/bin/bash

# Environment variables with defaults
CERT_TYPE="${CERT_TYPE:-self-signed}"
DOMAIN="${DOMAIN:-localhost}"
EMAIL="${EMAIL:-}"
STAGING="${STAGING:-true}"
CERT_BASE="/data/certificates"
CERT_DIR="$CERT_BASE/$DOMAIN"

# Setup logging infrastructure
setup_logging() {
    echo "[$(date -Iseconds)] [INFO] [CERTBOT] [INIT]: Initializing certificate operation logging..."
    
    # Ensure log files exist with proper permissions
    touch /data/logs/certbot/{operations,errors}.log
    chown certuser:loggroup /data/logs/certbot/*.log
    chmod 644 /data/logs/certbot/*.log
    
    echo "[$(date -Iseconds)] [INFO] [CERTBOT] [INIT]: Certificate logging initialized"
}

# Logging function
log_operation() {
    local level=$1
    local message=$2
    local timestamp=$(date -Iseconds)
    local log_entry="[$timestamp] [$level] [CERTBOT] [OPERATION]: $message"
    
    echo "$log_entry" | tee -a /data/logs/certbot/operations.log
    
    if [ "$level" = "ERROR" ]; then
        echo "$log_entry" | tee -a /data/logs/certbot/errors.log >&2
    fi
}

# Call logging setup
setup_logging

# Create certificate directory
mkdir -p "$CERT_DIR"

# Store domain info for other containers
echo "$DOMAIN" > "$CERT_BASE/domain.txt"

log_operation "INFO" "Starting certificate operation for domain: $DOMAIN (type: $CERT_TYPE)"

if [ "$CERT_TYPE" = "letsencrypt" ]; then
    log_operation "INFO" "Generating Let's Encrypt certificate for $DOMAIN"
    
    # Check required parameters
    if [ -z "$EMAIL" ]; then
        log_operation "ERROR" "EMAIL environment variable is required for Let's Encrypt"
        exit 1
    fi
    
    # Create writable directories for certbot
    mkdir -p /tmp/letsencrypt/config /tmp/letsencrypt/work /tmp/letsencrypt/logs
    
    # Build certbot command with custom directories
    CERTBOT_CMD="certbot certonly --non-interactive --agree-tos"
    CERTBOT_CMD="$CERTBOT_CMD --email $EMAIL"
    CERTBOT_CMD="$CERTBOT_CMD --standalone"
    CERTBOT_CMD="$CERTBOT_CMD -d $DOMAIN"
    CERTBOT_CMD="$CERTBOT_CMD --config-dir /tmp/letsencrypt/config"
    CERTBOT_CMD="$CERTBOT_CMD --work-dir /tmp/letsencrypt/work"
    CERTBOT_CMD="$CERTBOT_CMD --logs-dir /tmp/letsencrypt/logs"
    
    if [ "$STAGING" = "true" ]; then
        CERTBOT_CMD="$CERTBOT_CMD --staging"
    fi
    
    # Run certbot
    log_operation "INFO" "Executing certbot command: $CERTBOT_CMD"
    if $CERTBOT_CMD; then
        log_operation "INFO" "Certbot completed successfully"
    else
        log_operation "ERROR" "Certbot command failed"
        exit 1
    fi
    
    # Copy certificates to our directory
    if [ -d "/tmp/letsencrypt/config/live/$DOMAIN" ]; then
        cp -L "/tmp/letsencrypt/config/live/$DOMAIN/fullchain.pem" "$CERT_DIR/"
        cp -L "/tmp/letsencrypt/config/live/$DOMAIN/privkey.pem" "$CERT_DIR/"
        log_operation "INFO" "Let's Encrypt certificates copied to $CERT_DIR"
    else
        log_operation "ERROR" "Let's Encrypt certificates not found in expected location"
        exit 1
    fi
    
else
    log_operation "INFO" "Generating self-signed certificate for $DOMAIN"
    
    # Generate self-signed certificate
    if openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"; then
        log_operation "INFO" "Self-signed certificate generated successfully in $CERT_DIR"
    else
        log_operation "ERROR" "Failed to generate self-signed certificate"
        exit 1
    fi
fi

# Set proper permissions for certificates
log_operation "INFO" "Setting certificate permissions"
# Public certificate can be world-readable
chmod 644 "$CERT_DIR/fullchain.pem" 2>/dev/null || true
# Private key should only be readable by owner and group
chmod 640 "$CERT_DIR/privkey.pem" 2>/dev/null || true

# Ensure group ownership is correct (certuser might not have permission to chown)
# This will work because we're running as certuser which owns the files
chgrp certgroup "$CERT_DIR"/*.pem 2>/dev/null || true

# List generated certificates
log_operation "INFO" "Certificate operation completed successfully"
echo "Certificates in $CERT_DIR:"
ls -la "$CERT_DIR/" | tee -a /data/logs/certbot/operations.log

# Keep container running if no command specified
if [ $# -eq 0 ]; then
    exec /bin/bash
else
    exec "$@"
fi