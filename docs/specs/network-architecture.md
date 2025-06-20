# Network Architecture Specification

## Purpose
Define the network architecture, port mappings, and routing strategies for the containerized services.

## Scope
- Container network configuration
- Port mapping strategies
- Router integration for external access
- Service discovery patterns
- Security zones and isolation

## Requirements

### Functional Requirements
1. Support for Let's Encrypt validation through router
2. Service isolation with inter-service communication
3. External access to public services
4. Internal-only access for management services
5. IPv4 and IPv6 support

### Non-Functional Requirements
1. Minimal attack surface
2. Clear network segmentation
3. Support for non-root container execution
4. Compatibility with home router NAT
5. Scalable to multiple hosts

## Network Design

### Port Mapping Strategy
```
External (Router) → Internal (Host) → Container
Port 80          → Port 8080       → Port 80
Port 443         → Port 8443       → Port 443
```

### Service Port Allocations

| Service | Container Ports | Host Ports | External Ports | Protocol |
|---------|----------------|------------|----------------|----------|
| Apache  | 80, 443        | 8080, 8443 | 80, 443        | TCP      |
| DNS     | 53             | 53         | 53             | TCP/UDP  |
| Mail SMTP | 25, 587, 465 | 25, 587, 465 | 25, 587, 465 | TCP    |
| Mail IMAP | 143, 993     | 143, 993   | 143, 993       | TCP      |
| Mail POP3 | 110, 995     | 110, 995   | 110, 995       | TCP      |
| Certbot | 80             | 8080       | 80             | TCP      |

## Container Network Modes

### Bridge Network (Default)
```bash
# Create custom bridge network
podman network create \
    --driver bridge \
    --subnet 172.20.0.0/16 \
    --gateway 172.20.0.1 \
    podplay-net

# Run container on custom network
podman run -d \
    --network podplay-net \
    --name apache \
    -p 8080:80 \
    podplay-apache-debian:latest
```

### Host Network Mode
```bash
# For services requiring host network access
podman run -d \
    --network host \
    --name dns \
    podplay-bind-debian:latest
```

## Router Configuration

### Port Forwarding Rules
```
# HTTP/HTTPS for web services and Let's Encrypt
External 0.0.0.0:80  → Internal 192.168.1.100:8080
External 0.0.0.0:443 → Internal 192.168.1.100:8443

# Mail services
External 0.0.0.0:25  → Internal 192.168.1.100:25
External 0.0.0.0:587 → Internal 192.168.1.100:587
External 0.0.0.0:465 → Internal 192.168.1.100:465
External 0.0.0.0:993 → Internal 192.168.1.100:993
External 0.0.0.0:995 → Internal 192.168.1.100:995

# DNS (if serving external queries)
External 0.0.0.0:53  → Internal 192.168.1.100:53
```

### Let's Encrypt Validation Flow
```
1. Let's Encrypt → Router:80
2. Router:80 → Host:8080 (NAT)
3. Host:8080 → Certbot:80 (Port mapping)
4. Certbot serves challenge response
5. Certificate issued
```

## Service Discovery

### Internal DNS Names
```bash
# /etc/hosts entries or internal DNS
172.20.0.10 apache.podplay.local
172.20.0.11 mail.podplay.local
172.20.0.12 dns.podplay.local
172.20.0.13 certbot.podplay.local
```

### Environment-Based Discovery
```bash
# Pass service endpoints via environment
MAIL_HOST=mail.podplay.local
MAIL_PORT=25
DNS_SERVER=dns.podplay.local
```

### Container DNS Resolution
```yaml
# Podman DNS configuration
dns:
  - 172.20.0.12  # Internal DNS
  - 8.8.8.8      # Fallback
```

## Security Zones

### DMZ Services (External Access)
```
Network: podplay-dmz
Subnet: 172.20.1.0/24
Services:
  - Apache (Web)
  - Mail (SMTP/IMAP/POP3)
  - DNS (Public queries)
```

### Internal Services
```
Network: podplay-internal
Subnet: 172.20.2.0/24
Services:
  - Database
  - Cache
  - Internal APIs
```

### Management Network
```
Network: podplay-mgmt
Subnet: 172.20.3.0/24
Services:
  - Monitoring
  - Logging
  - Configuration
```

## Firewall Rules

### Host Firewall (iptables/nftables)
```bash
# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow specific services
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT  # HTTP
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT  # HTTPS
iptables -A INPUT -p tcp --dport 25 -j ACCEPT    # SMTP
iptables -A INPUT -p tcp --dport 587 -j ACCEPT   # Submission
iptables -A INPUT -p tcp --dport 993 -j ACCEPT   # IMAPS
iptables -A INPUT -p udp --dport 53 -j ACCEPT    # DNS

# Default deny
iptables -A INPUT -j DROP
```

### Container Network Policies
```bash
# Isolate networks
podman network create --internal podplay-internal

# Allow specific inter-container communication
podman run -d \
    --network podplay-net \
    --network-alias mail \
    --name mail \
    podplay-mail-debian:latest
```

## Load Balancing

### Multiple Apache Instances
```bash
# Create load balancer network
podman network create podplay-lb

# Run multiple Apache instances
for i in 1 2 3; do
    podman run -d \
        --network podplay-lb \
        --name apache-$i \
        podplay-apache-debian:latest
done

# Run HAProxy load balancer
podman run -d \
    --network podplay-lb \
    -p 8080:80 \
    -v haproxy-config:/usr/local/etc/haproxy \
    haproxy:latest
```

### HAProxy Configuration
```
global
    maxconn 4096

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

backend apache_servers
    balance roundrobin
    server apache1 apache-1:80 check
    server apache2 apache-2:80 check
    server apache3 apache-3:80 check

frontend http_front
    bind *:80
    default_backend apache_servers
```

## IPv6 Support

### Enable IPv6 in Podman
```bash
# Create IPv6-enabled network
podman network create \
    --ipv6 \
    --subnet fd00:dead:beef::/64 \
    podplay-ipv6

# Run with IPv6
podman run -d \
    --network podplay-ipv6 \
    --sysctl net.ipv6.conf.all.disable_ipv6=0 \
    podplay-apache-debian:latest
```

### Dual Stack Configuration
```
# Apache listen configuration
Listen 80
Listen [::]:80

<VirtualHost *:80 [::]:80>
    ServerName example.com
    # ...
</VirtualHost>
```

## Monitoring and Troubleshooting

### Network Debugging Tools
```bash
# Check container network
podman inspect <container> | jq '.[0].NetworkSettings'

# Test connectivity
podman exec apache ping mail.podplay.local

# Check port bindings
podman port apache

# Network statistics
podman exec apache ss -tulpn
```

### Traffic Analysis
```bash
# Capture container traffic
podman exec apache tcpdump -i eth0 -w /tmp/capture.pcap

# Monitor bandwidth
podman exec apache iftop -i eth0
```

## Performance Optimization

### Network Tuning
```bash
# Increase network buffers
sysctl -w net.core.rmem_max=134217728
sysctl -w net.core.wmem_max=134217728
sysctl -w net.ipv4.tcp_rmem="4096 87380 134217728"
sysctl -w net.ipv4.tcp_wmem="4096 65536 134217728"

# Enable TCP fast open
sysctl -w net.ipv4.tcp_fastopen=3
```

### Container Network Performance
```bash
# Use host network for performance-critical services
podman run -d \
    --network host \
    --name high-perf-service \
    service:latest

# Enable SR-IOV for network acceleration
podman run -d \
    --device /dev/vfio/1 \
    --name accelerated-service \
    service:latest
```

## Disaster Recovery

### Network Backup
```bash
# Export network configuration
podman network inspect podplay-net > network-config.json

# Recreate network from backup
podman network create \
    --driver bridge \
    --subnet $(jq -r '.[0].Subnets[0].Subnet' network-config.json) \
    podplay-net
```

### Service Migration
```bash
# Export running containers
for container in $(podman ps -q); do
    podman generate systemd $container > $container.service
done

# Import on new host
for service in *.service; do
    cp $service /etc/systemd/system/
    systemctl enable $service
    systemctl start $service
done
```

## Future Enhancements

1. **Service Mesh**
   - Istio/Linkerd integration
   - Automatic mTLS
   - Traffic management
   - Observability

2. **SDN Integration**
   - OpenVSwitch support
   - VXLAN overlays
   - Network virtualization
   - Multi-host networking

3. **Advanced Security**
   - Network segmentation
   - Micro-segmentation
   - Zero-trust networking
   - DDoS protection