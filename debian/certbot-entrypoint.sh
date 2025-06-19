#!/bin/bash

# Environment variables with defaults
CERT_TYPE="${CERT_TYPE:-self-signed}"
DOMAIN="${DOMAIN:-localhost}"
EMAIL="${EMAIL:-}"
STAGING="${STAGING:-true}"
CERT_BASE="/data/certificates"
CERT_DIR="$CERT_BASE/$DOMAIN"

# Create certificate directory
mkdir -p "$CERT_DIR"

# Store domain info for other containers
echo "$DOMAIN" > "$CERT_BASE/domain.txt"

if [ "$CERT_TYPE" = "letsencrypt" ]; then
    echo "Generating Let's Encrypt certificate for $DOMAIN"
    
    # Check required parameters
    if [ -z "$EMAIL" ]; then
        echo "Error: EMAIL environment variable is required for Let's Encrypt"
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
    $CERTBOT_CMD
    
    # Copy certificates to our directory
    if [ -d "/tmp/letsencrypt/config/live/$DOMAIN" ]; then
        cp -L "/tmp/letsencrypt/config/live/$DOMAIN/fullchain.pem" "$CERT_DIR/"
        cp -L "/tmp/letsencrypt/config/live/$DOMAIN/privkey.pem" "$CERT_DIR/"
        echo "Let's Encrypt certificates copied to $CERT_DIR"
    else
        echo "Error: Let's Encrypt certificates not found in expected location"
        exit 1
    fi
    
else
    echo "Generating self-signed certificate for $DOMAIN"
    
    # Generate self-signed certificate
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"
    
    echo "Self-signed certificate generated in $CERT_DIR"
fi

# Set proper permissions for certificates
# Public certificate can be world-readable
chmod 644 "$CERT_DIR/fullchain.pem" 2>/dev/null || true
# Private key should only be readable by owner and group
chmod 640 "$CERT_DIR/privkey.pem" 2>/dev/null || true

# Ensure group ownership is correct (certuser might not have permission to chown)
# This will work because we're running as certuser which owns the files
chgrp certgroup "$CERT_DIR"/*.pem 2>/dev/null || true

# List generated certificates
echo "Certificates in $CERT_DIR:"
ls -la "$CERT_DIR/"

# Keep container running if no command specified
if [ $# -eq 0 ]; then
    exec /bin/bash
else
    exec "$@"
fi