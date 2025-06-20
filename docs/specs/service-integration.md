# Service Integration Specification

## Purpose
Define standard patterns for service configuration, startup dependencies, and inter-service communication.

## Scope
- Environment variable conventions
- Configuration templating methodology
- Service dependency management
- Health check implementations
- Startup sequencing

## Requirements

### Functional Requirements
1. Dynamic service configuration through environment variables
2. Template-based configuration file generation
3. Dependency validation before service startup
4. Graceful handling of missing dependencies
5. Service health monitoring

### Non-Functional Requirements
1. Consistent patterns across all services
2. Clear error messages for misconfiguration
3. Fast startup times
4. Minimal resource overhead

## Design Patterns

### Environment Variable Hierarchy
```bash
# Global variables (all services)
DOMAIN=example.com
LOG_LEVEL=info

# Service-specific prefixes
APACHE_SERVER_ADMIN=admin@example.com
BIND_FORWARDERS=8.8.8.8,8.8.4.4
MAIL_HOSTNAME=mail.example.com

# Certificate paths (override defaults)
CERT_PATH=/data/certificates/${DOMAIN}
```

### Configuration Template Pattern
```bash
# Template file: config.template
server {
    server_name ${DOMAIN};
    ssl_certificate ${CERT_PATH}/fullchain.pem;
    ssl_certificate_key ${CERT_PATH}/privkey.pem;
}

# Processing in entrypoint.sh
envsubst < config.template > /etc/service/config.conf
```

## Implementation Guidelines

### Standard Entrypoint Structure
```bash
#!/bin/bash
set -e

# 1. Environment validation
validate_environment() {
    required_vars="DOMAIN"
    for var in $required_vars; do
        if [ -z "${!var}" ]; then
            echo "Error: $var is not set"
            exit 1
        fi
    done
}

# 2. Wait for dependencies
wait_for_certificates() {
    echo "Waiting for SSL certificates..."
    timeout=300
    elapsed=0
    while [ ! -f "${CERT_PATH}/fullchain.pem" ]; do
        if [ $elapsed -ge $timeout ]; then
            echo "Error: Certificate wait timeout"
            exit 1
        fi
        echo "Certificates not found. Retrying in 5 seconds..."
        sleep 5
        elapsed=$((elapsed + 5))
    done
}

# 3. Generate configuration
generate_config() {
    echo "Generating configuration..."
    envsubst < /templates/config.template > /etc/service/config.conf
}

# 4. Validate configuration
validate_config() {
    echo "Validating configuration..."
    service-check-config || exit 1
}

# 5. Start service
start_service() {
    echo "Starting service..."
    exec service-binary --foreground
}

# Main execution
validate_environment
wait_for_certificates
generate_config
validate_config
start_service
```

### Dependency Management

#### Certificate Dependencies
```bash
# Check certificate availability
check_certificates() {
    local required_files="fullchain.pem privkey.pem"
    for file in $required_files; do
        if [ ! -r "${CERT_PATH}/${file}" ]; then
            return 1
        fi
    done
    return 0
}
```

#### Network Dependencies
```bash
# Wait for DNS resolution
wait_for_dns() {
    while ! nslookup ${DOMAIN} >/dev/null 2>&1; do
        echo "Waiting for DNS..."
        sleep 2
    done
}
```

#### Service Dependencies
```bash
# Wait for another service
wait_for_service() {
    local host=$1
    local port=$2
    while ! nc -z $host $port >/dev/null 2>&1; do
        echo "Waiting for $host:$port..."
        sleep 2
    done
}
```

## Health Check Patterns

### HTTP Health Check
```bash
# Apache health check
curl -f http://localhost/health || exit 1
```

### TCP Port Check
```bash
# Mail service health check
nc -z localhost 25 && nc -z localhost 143 || exit 1
```

### Process Check
```bash
# DNS service health check
pgrep named >/dev/null || exit 1
```

### Container Health Check
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1
```

## Configuration Validation

### Service-Specific Validators
```bash
# Apache
apache2ctl configtest

# BIND
named-checkconf /etc/bind/named.conf
named-checkzone ${DOMAIN} /etc/bind/zones/${DOMAIN}.zone

# Postfix
postfix check

# Dovecot
doveconf -n >/dev/null
```

## Error Handling

### Graceful Degradation
```bash
# Fall back to HTTP if certificates not available
if [ ! -f "${CERT_PATH}/fullchain.pem" ]; then
    echo "Warning: Running without SSL"
    use_ssl=false
fi
```

### Retry Logic
```bash
retry_with_backoff() {
    local max_attempts=5
    local attempt=1
    local wait_time=1
    
    while [ $attempt -le $max_attempts ]; do
        if "$@"; then
            return 0
        fi
        echo "Attempt $attempt failed. Retrying in ${wait_time}s..."
        sleep $wait_time
        attempt=$((attempt + 1))
        wait_time=$((wait_time * 2))
    done
    return 1
}
```

## Logging Standards

### Log Format
```bash
# Timestamp [Level] Service: Message
2024-01-20T10:30:45Z [INFO] Apache: Configuration validated successfully
2024-01-20T10:30:46Z [ERROR] Apache: Certificate not found at /data/certificates/example.com/fullchain.pem
```

### Log Levels
- **ERROR**: Service cannot start or continue
- **WARN**: Degraded functionality
- **INFO**: Normal operations
- **DEBUG**: Detailed troubleshooting

## Testing Considerations

1. **Unit Tests**
   - Environment variable validation
   - Configuration template processing
   - Dependency check functions

2. **Integration Tests**
   - Service startup sequence
   - Dependency wait behavior
   - Configuration generation

3. **Failure Tests**
   - Missing environment variables
   - Invalid configurations
   - Unavailable dependencies

## Service Communication

### Internal DNS
```bash
# Service discovery through DNS
apache.internal -> 172.16.0.10
mail.internal   -> 172.16.0.11
dns.internal    -> 172.16.0.12
```

### Shared Volumes
```yaml
# Read-only certificate access
volumes:
  - certs:/data/certificates:ro
  
# Shared data volume
volumes:
  - shared-data:/data/shared:rw
```

## Future Enhancements

1. **Service Mesh**
   - Envoy proxy integration
   - mTLS between services
   - Circuit breaker patterns

2. **Configuration Management**
   - Consul integration
   - Dynamic reconfiguration
   - Configuration versioning

3. **Observability**
   - OpenTelemetry integration
   - Distributed tracing
   - Metrics collection