#!/bin/bash
set -e

# Set default environment variables
export DOMAIN_NAME=${DOMAIN_NAME:-"lab.sethlakowske.com"}
export DOMAIN_IP=${DOMAIN_IP:-"127.0.0.1"}
export DNS_FORWARDERS=${DNS_FORWARDERS:-"8.8.8.8; 8.8.4.4; 1.1.1.1; 1.0.0.1"}

echo "Starting BIND DNS server for domain: $DOMAIN_NAME"
echo "Domain IP: $DOMAIN_IP"
echo "DNS Forwarders: $DNS_FORWARDERS"

# Create necessary directories
mkdir -p /var/cache/bind /var/log/bind /etc/bind/zones

# Format forwarders for BIND config (replace semicolons with proper formatting)
export DNS_FORWARDERS_FORMATTED=$(echo "$DNS_FORWARDERS" | sed 's/;/;\n        /g' | sed 's/$/;/' | sed 's/;;$/;/')

# Process named.conf.options template
echo "Configuring BIND options..."
envsubst '${DNS_FORWARDERS_FORMATTED}' < /etc/bind/named.conf.options.template > /etc/bind/named.conf.options

# Process named.conf.local template
echo "Configuring local zones..."
envsubst '${DOMAIN_NAME}' < /etc/bind/named.conf.local.template > /etc/bind/named.conf.local

# Process zone file template
echo "Creating zone file for $DOMAIN_NAME..."
export SERIAL_NUMBER=$(date +%Y%m%d)01
envsubst '${DOMAIN_NAME} ${DOMAIN_IP} ${SERIAL_NUMBER}' < /etc/bind/db.domain.template > /etc/bind/zones/db.${DOMAIN_NAME}

# Create reverse DNS zone file (optional)
cat > /etc/bind/zones/db.10 << EOF
\$TTL    604800
@       IN      SOA     $DOMAIN_NAME. admin.$DOMAIN_NAME. (
                        $(date +%Y%m%d)01    ; Serial
                        604800              ; Refresh
                        86400               ; Retry
                        2419200             ; Expire
                        604800 )            ; Negative Cache TTL

; Name server
@       IN      NS      ns1.$DOMAIN_NAME.

; PTR records for reverse lookup
1       IN      PTR     $DOMAIN_NAME.
EOF

# Set proper permissions
chown -R bind:bind /etc/bind /var/cache/bind /var/log/bind
chmod 644 /etc/bind/*.conf
chmod 644 /etc/bind/zones/*

# Check BIND configuration
echo "Checking BIND configuration..."
if ! named-checkconf; then
    echo "ERROR: BIND configuration check failed"
    echo "=== named.conf.options ==="
    cat /etc/bind/named.conf.options
    echo "=== named.conf.local ==="
    cat /etc/bind/named.conf.local
    exit 1
fi

# Check zone files
echo "Checking zone files..."
if ! named-checkzone "$DOMAIN_NAME" "/etc/bind/zones/db.${DOMAIN_NAME}"; then
    echo "ERROR: Zone file check failed for $DOMAIN_NAME"
    cat "/etc/bind/zones/db.${DOMAIN_NAME}"
    exit 1
fi

echo ""
echo "DNS server configuration complete!"
echo "  - Domain: $DOMAIN_NAME"
echo "  - Authoritative for: $DOMAIN_NAME"
echo "  - Forwarders: $DNS_FORWARDERS"
echo "  - Listening on: port 53 (UDP/TCP)"
echo "  - Zone file: /etc/bind/zones/db.${DOMAIN_NAME}"
echo ""

# Start BIND in foreground
echo "Starting BIND DNS server..."
exec /usr/sbin/named -g -u bind