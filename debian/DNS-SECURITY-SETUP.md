# DNS Security Setup for PodPlay

This guide covers implementing rate limiting in BIND and fail2ban integration to protect against DNS abuse.

## 1. BIND Rate Limiting (Already Implemented)

The rate limiting configuration has been added to `debian/bind-config/named.conf.options.template`:

```
rate-limit {
    responses-per-second 5;     // Max 5 responses per second per client
    errors-per-second 2;        // Max 2 NXDOMAIN/errors per second
    nxdomains-per-second 2;     // Max 2 NXDOMAIN responses per second
    all-per-second 10;          // Overall limit per client
    window 10;                  // Track over 10 second windows
    slip 2;                     // Drop every other response when over limit
    qps-scale 250;              // Scale limits when server is busy
    exempt-clients { 127.0.0.1; ::1; };  // Don't rate limit localhost
    log-only no;                // Actually enforce limits (not just log)
};
```

To apply this configuration:

```bash
# Rebuild the BIND image with new configuration
make bind

# Restart the pod
make pod-down && make pod-up
```

## 2. Fail2ban Setup (Manual Installation Required)

### Install fail2ban on the host:
```bash
sudo apt update
sudo apt install fail2ban
```

### Install the filter and jail configurations:
```bash
# Copy filter configuration
sudo cp /home/seth/podplay/debian/fail2ban-bind-filter.conf /etc/fail2ban/filter.d/bind-dns-abuse.conf

# Copy jail configuration
sudo cp /home/seth/podplay/debian/fail2ban-bind-jail.conf /etc/fail2ban/jail.d/bind.conf
```

### Restart fail2ban:
```bash
sudo systemctl restart fail2ban
sudo systemctl status fail2ban
```

### Verify fail2ban is monitoring:
```bash
# Check jail status
sudo fail2ban-client status bind-dns-abuse
sudo fail2ban-client status bind-any-abuse

# Watch for bans
sudo tail -f /var/log/fail2ban.log
```

## 3. Testing Rate Limiting

Test that rate limiting is working:
```bash
# This should trigger rate limiting after 5 queries
for i in {1..20}; do dig @localhost sethcore.com; done

# Check BIND logs for rate limit messages
podman exec podplay-bind tail -20 /data/logs/bind/general.log | grep "rate limit"
```

## 4. Monitoring

### Check BIND rate limiting:
```bash
# View rate limit drops
podman exec podplay-bind rndc stats
podman exec podplay-bind cat /var/cache/bind/named.stats | grep -A5 "Rate limit"
```

### Check fail2ban bans:
```bash
# List current bans
sudo fail2ban-client status bind-dns-abuse
sudo iptables -L -n | grep bind
```

## 5. Important Limitations

**Pod Networking Issue**: Currently, all external queries appear to come from the pod gateway IP (10.89.0.17) rather than real client IPs. This means:

1. BIND rate limiting works but applies to all external traffic as one client
2. Fail2ban cannot distinguish between different external clients

To fix this, you would need to:
- Switch BIND container to use host networking, OR
- Implement a DNS proxy that preserves client IPs

## 6. Uninstalling

If you need to remove the security measures:

```bash
# Remove fail2ban rules
sudo rm /etc/fail2ban/filter.d/bind-dns-abuse.conf
sudo rm /etc/fail2ban/jail.d/bind.conf
sudo systemctl restart fail2ban

# Remove rate limiting from BIND
# Edit debian/bind-config/named.conf.options.template and remove the rate-limit block
# Then rebuild: make bind && make pod-down && make pod-up
```