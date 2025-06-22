# Project Configuration

## User Settings
- **Domain**: lab.sethlakowske.com
- **Let's Encrypt Email**: lakowske@gmail.com

## Network Configuration
- **Router Port Forwarding**: External ports 80 and 443 are forwarded to local ports 8080 and 8443
- **Container Host Bindings**: 
  - Web services: Use `-p 8080:80 -p 8443:443` for Apache/HTTP services
  - Certificate services: Use `-p 8080:80` for Let's Encrypt validation (certbot container)
- This allows Let's Encrypt validation to work through the router while keeping services on non-privileged ports locally
- **Important**: For Let's Encrypt certificate generation, run the certbot container with `--user root` and `-p 8080:80` to allow proper port binding and validation

## Best Practices

### Container Volumes
- Always use named volumes instead of host mounts when possible
- Host mounts can cause UID and permission problems
- Named volumes provide better isolation and avoid filesystem permission conflicts

### Examples
```bash
# Preferred: Named volume
podman volume create certs
podman run -v certs:/data/certificates ...

# Avoid: Host mount (causes permission issues)
podman run -v ./certificates:/data/certificates ...
```

## Certificate Volume Management

### Important: Preserve Production Certificates
- **NEVER** remove the `certs` volume containing production Let's Encrypt certificates
- Let's Encrypt has rate limits (5 certificates per domain per week)
- Removing the certificates volume will force re-generation and may hit rate limits
- Only remove the certificates volume during initial development or if certificates are corrupted

### Safe Development Practices
```bash
# Safe: Only rebuild images, preserve volumes
make clean && make all

# Safe: Stop and restart pods without removing volumes
make pod-down && make pod-up

# DANGER: Avoid this in production - will trigger new certificate generation
make clean-volumes

# Safe alternative: Only clean specific volumes if needed
podman volume rm logs user-data  # Keep certs volume intact
```

## Service Operations

### Quick Reference
- The **QUICKSTART.md** file contains the complete deployment workflow and troubleshooting commands
- When asked to operate PodPlay services, refer to QUICKSTART.md for:
  - Step-by-step deployment workflow using Make targets
  - Management commands for pod operations
  - Troubleshooting procedures for common issues
  - Service access information (ports, URLs)

### Key Commands from QUICKSTART.md
```bash
# Deployment workflow
make all              # Build all images
make volumes          # Create volumes
make pod-init         # Generate certificates
make pod-cert-cleanup # Remove certificate pod
make pod-up           # Start services

# Management
make pod-status       # Check status
make pod-logs         # View logs
make pod-down         # Stop services
```