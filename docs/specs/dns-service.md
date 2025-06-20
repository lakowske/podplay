# DNS Service Specification

## Purpose
Define the requirements and implementation for the BIND DNS server container service.

## Scope
- Authoritative DNS server configuration
- Zone file management
- Dynamic configuration through templates
- DNSSEC support preparation
- Monitoring and logging

## Requirements

### Functional Requirements
1. Serve as authoritative DNS for configured domains
2. Support forward and reverse DNS zones
3. Dynamic zone file generation from templates
4. DNS forwarding for external queries
5. Zone transfer restrictions

### Non-Functional Requirements
1. Fast query response times (<10ms local)
2. Secure by default configuration
3. Minimal memory footprint
4. Support for high query rates
5. < 100MB container image

## Design Decisions

### Zone File Structure
```
/etc/bind/
├── named.conf
├── named.conf.local
├── named.conf.options
└── zones/
    ├── example.com.zone
    ├── db.192.168.1
    └── templates/
        ├── forward.zone.template
        └── reverse.zone.template
```

### Configuration Architecture
- **named.conf**: Main configuration file
- **named.conf.options**: Global server options
- **named.conf.local**: Zone definitions
- **Zone templates**: Environment variable substitution

## Implementation

### Dockerfile Structure
```dockerfile
FROM base-debian:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    bind9 \
    bind9-utils \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Add bind user to certgroup (for future DNSSEC)
RUN usermod -a -G certgroup bind

# Create directories
RUN mkdir -p /etc/bind/zones/templates && \
    chown -R bind:bind /etc/bind

COPY configs/ /etc/bind/templates/
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

EXPOSE 53/tcp 53/udp

ENTRYPOINT ["/entrypoint.sh"]
```

### Named Configuration Options
```bash
# named.conf.options.template
options {
    directory "/var/cache/bind";
    
    # DNS forwarders
    forwarders {
        ${DNS_FORWARDERS};
    };
    
    # Security options
    dnssec-validation auto;
    auth-nxdomain no;
    
    # Listen on all interfaces
    listen-on { any; };
    listen-on-v6 { any; };
    
    # Allow queries from anywhere (for public DNS)
    # Restrict for internal use
    allow-query { any; };
    
    # Hide version
    version "DNS Server";
    
    # Disable zone transfers by default
    allow-transfer { none; };
    
    # Rate limiting
    rate-limit {
        responses-per-second 10;
        errors-per-second 5;
        nxdomains-per-second 5;
    };
};
```

### Forward Zone Template
```bash
# forward.zone.template
$TTL    604800
@       IN      SOA     ns1.${DOMAIN}. admin.${DOMAIN}. (
                     ${SERIAL}         ; Serial (YYYYMMDDNN)
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL

; Name servers
@       IN      NS      ns1.${DOMAIN}.
@       IN      NS      ns2.${DOMAIN}.

; A records
@       IN      A       ${DOMAIN_IP}
ns1     IN      A       ${DOMAIN_IP}
ns2     IN      A       ${DOMAIN_IP}
www     IN      A       ${DOMAIN_IP}
mail    IN      A       ${DOMAIN_IP}

; Mail records
@       IN      MX      10 mail.${DOMAIN}.

; TXT records
@       IN      TXT     "v=spf1 mx -all"
_dmarc  IN      TXT     "v=DMARC1; p=quarantine; rua=mailto:dmarc@${DOMAIN}"

; Service records
_smtp._tcp      IN      SRV     0 0 25 mail.${DOMAIN}.
_submission._tcp IN     SRV     0 0 587 mail.${DOMAIN}.
_imaps._tcp     IN      SRV     0 0 993 mail.${DOMAIN}.
_pop3s._tcp     IN      SRV     0 0 995 mail.${DOMAIN}.
```

### Reverse Zone Template
```bash
# reverse.zone.template
$TTL    604800
@       IN      SOA     ns1.${DOMAIN}. admin.${DOMAIN}. (
                     ${SERIAL}         ; Serial
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL

; Name servers
@       IN      NS      ns1.${DOMAIN}.
@       IN      NS      ns2.${DOMAIN}.

; PTR records
${PTR_RECORD}   IN      PTR     ${DOMAIN}.
```

### Zone Configuration
```bash
# named.conf.local.template
zone "${DOMAIN}" {
    type master;
    file "/etc/bind/zones/${DOMAIN}.zone";
    allow-transfer { ${SECONDARY_NS}; };
    also-notify { ${SECONDARY_NS}; };
};

zone "${REVERSE_ZONE}.in-addr.arpa" {
    type master;
    file "/etc/bind/zones/db.${REVERSE_ZONE}";
    allow-transfer { ${SECONDARY_NS}; };
};
```

### Entrypoint Script
```bash
#!/bin/bash
set -e

# Generate serial number (YYYYMMDDNN format)
generate_serial() {
    echo "$(date +%Y%m%d)01"
}

# Calculate reverse zone from IP
calculate_reverse_zone() {
    local ip=$1
    echo "$ip" | awk -F. '{print $3"."$2"."$1}'
}

# Calculate PTR record
calculate_ptr_record() {
    local ip=$1
    echo "$ip" | awk -F. '{print $4}'
}

# Generate zone files
generate_zones() {
    echo "Generating DNS zones for ${DOMAIN}..."
    
    # Set variables
    export SERIAL=$(generate_serial)
    export REVERSE_ZONE=$(calculate_reverse_zone ${DOMAIN_IP})
    export PTR_RECORD=$(calculate_ptr_record ${DOMAIN_IP})
    
    # Forward zone
    envsubst < /etc/bind/templates/forward.zone.template > /etc/bind/zones/${DOMAIN}.zone
    
    # Reverse zone
    envsubst < /etc/bind/templates/reverse.zone.template > /etc/bind/zones/db.${REVERSE_ZONE}
    
    # Named configuration
    envsubst < /etc/bind/templates/named.conf.options.template > /etc/bind/named.conf.options
    envsubst < /etc/bind/templates/named.conf.local.template > /etc/bind/named.conf.local
}

# Validate configuration
validate_config() {
    echo "Validating BIND configuration..."
    named-checkconf
    named-checkzone ${DOMAIN} /etc/bind/zones/${DOMAIN}.zone
    named-checkzone ${REVERSE_ZONE}.in-addr.arpa /etc/bind/zones/db.${REVERSE_ZONE}
}

# Fix permissions
fix_permissions() {
    chown -R bind:bind /etc/bind
    chmod 640 /etc/bind/zones/*
}

# Start BIND
start_bind() {
    echo "Starting BIND DNS server..."
    exec named -g -u bind
}

# Main
generate_zones
validate_config
fix_permissions
start_bind
```

## Advanced Configuration

### DNSSEC Implementation
```bash
# Generate KSK (Key Signing Key)
dnssec-keygen -a RSASHA256 -b 2048 -f KSK ${DOMAIN}

# Generate ZSK (Zone Signing Key)
dnssec-keygen -a RSASHA256 -b 1024 ${DOMAIN}

# Sign zone
dnssec-signzone -o ${DOMAIN} -k KSK.key ${DOMAIN}.zone ZSK.key

# Update configuration
zone "${DOMAIN}" {
    type master;
    file "/etc/bind/zones/${DOMAIN}.zone.signed";
    key-directory "/etc/bind/keys";
    auto-dnssec maintain;
    inline-signing yes;
};
```

### Views for Split-Horizon DNS
```bash
view "internal" {
    match-clients { 192.168.0.0/16; 10.0.0.0/8; };
    
    zone "example.com" {
        type master;
        file "/etc/bind/zones/internal/example.com.zone";
    };
};

view "external" {
    match-clients { any; };
    
    zone "example.com" {
        type master;
        file "/etc/bind/zones/external/example.com.zone";
    };
};
```

## Security Configuration

### Access Control Lists
```bash
acl "trusted" {
    localhost;
    192.168.0.0/16;
    10.0.0.0/8;
};

options {
    allow-query { any; };
    allow-recursion { trusted; };
    allow-query-cache { trusted; };
};
```

### Response Rate Limiting
```bash
rate-limit {
    responses-per-second 10;
    errors-per-second 5;
    nxdomains-per-second 5;
    slip 2;
    window 5;
    qps-scale 250;
    exempt-clients { trusted; };
};
```

## Monitoring and Logging

### Logging Configuration
```bash
logging {
    channel default_log {
        file "/var/log/bind/default.log" versions 3 size 5m;
        severity info;
        print-time yes;
        print-severity yes;
        print-category yes;
    };
    
    channel query_log {
        file "/var/log/bind/query.log" versions 3 size 10m;
        severity info;
        print-time yes;
    };
    
    category default { default_log; };
    category queries { query_log; };
};
```

### Statistics
```bash
statistics-channels {
    inet 127.0.0.1 port 8080 allow { localhost; };
};
```

## Testing Procedures

### Basic DNS Queries
```bash
# Test forward lookup
dig @localhost example.com

# Test reverse lookup
dig @localhost -x 192.168.1.10

# Test specific record types
dig @localhost example.com MX
dig @localhost example.com TXT
```

### Zone Transfer Testing
```bash
# Test zone transfer (should fail from unauthorized host)
dig @localhost example.com AXFR
```

### Performance Testing
```bash
# DNS performance test
dnsperf -s localhost -d queries.txt -c 10 -T 10
```

## Container Integration

### Running the Container
```bash
podman run -d \
    --name dns \
    -p 53:53/tcp \
    -p 53:53/udp \
    -v dns-config:/etc/bind \
    -v dns-logs:/var/log/bind \
    -e DOMAIN=example.com \
    -e DOMAIN_IP=192.168.1.10 \
    -e DNS_FORWARDERS="8.8.8.8; 8.8.4.4" \
    -e SECONDARY_NS="192.168.1.11" \
    podplay-bind-debian:latest
```

### Health Check
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD dig @localhost example.com || exit 1
```

## Future Enhancements

1. **Advanced Features**
   - Dynamic DNS updates (RFC 2136)
   - DNS over HTTPS (DoH)
   - DNS over TLS (DoT)
   - GeoIP-based responses

2. **Management**
   - Web-based zone editor
   - API for zone management
   - Automated DNSSEC key rotation
   - Zone file versioning

3. **High Availability**
   - Master-slave replication
   - Anycast deployment
   - Automatic failover
   - Zone synchronization