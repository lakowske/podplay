#!/bin/bash
# Setup logrotate for Podplay services
# This script should be run on the host system to manage log rotation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGROTATE_CONFIG="$SCRIPT_DIR/debian/logrotate.conf"
LOGROTATE_DEST="/etc/logrotate.d/podplay"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Check if logrotate config exists
if [ ! -f "$LOGROTATE_CONFIG" ]; then
    echo "Error: Logrotate configuration not found at $LOGROTATE_CONFIG"
    exit 1
fi

echo "Setting up logrotate for Podplay services..."

# Copy logrotate configuration
cp "$LOGROTATE_CONFIG" "$LOGROTATE_DEST"
chown root:root "$LOGROTATE_DEST"
chmod 644 "$LOGROTATE_DEST"

echo "Logrotate configuration installed to $LOGROTATE_DEST"

# Test the configuration
echo "Testing logrotate configuration..."
if logrotate -d "$LOGROTATE_DEST"; then
    echo "✓ Logrotate configuration is valid"
else
    echo "✗ Logrotate configuration has errors"
    exit 1
fi

# Check if logrotate is enabled and running
if systemctl is-enabled logrotate.timer >/dev/null 2>&1; then
    echo "✓ Logrotate timer is enabled"
else
    echo "! Logrotate timer is not enabled, enabling now..."
    systemctl enable logrotate.timer
fi

if systemctl is-active logrotate.timer >/dev/null 2>&1; then
    echo "✓ Logrotate timer is running"
else
    echo "! Logrotate timer is not running, starting now..."
    systemctl start logrotate.timer
fi

# Show next logrotate run time
echo ""
echo "Logrotate setup complete!"
echo "Next scheduled run: $(systemctl list-timers logrotate.timer --no-pager | grep logrotate.timer | awk '{print $1, $2}')"

# Create a manual test script
cat > /usr/local/bin/test-podplay-logrotate << 'EOF'
#!/bin/bash
echo "Testing Podplay logrotate configuration..."
logrotate -d /etc/logrotate.d/podplay
echo ""
echo "To force rotation (for testing):"
echo "logrotate -f /etc/logrotate.d/podplay"
EOF

chmod +x /usr/local/bin/test-podplay-logrotate

echo ""
echo "Additional commands:"
echo "  - Test configuration: test-podplay-logrotate"
echo "  - Force rotation: logrotate -f /etc/logrotate.d/podplay"
echo "  - Check timer status: systemctl status logrotate.timer"