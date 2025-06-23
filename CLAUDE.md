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

## Common Deployment States

### Typical Scenarios
When bringing up the PodPlay pod, you'll usually be in one of these states:

1. **Existing Deployment with Data** (Most Common)
   - Volumes already exist with certificates and user data
   - Just need to rebuild images and restart services
   ```bash
   make clean && make all     # Rebuild images only
   make pod-down && make pod-up  # Restart with existing volumes
   ```

2. **Fresh Installation** (Rare)
   - No existing volumes or certificates
   - Need full initialization workflow
   ```bash
   make all              # Build images
   make volumes          # Create all volumes
   make pod-init         # Generate certificates
   make pod-cert-cleanup # Clean up cert pod
   make pod-up           # Start services
   ```

3. **Partial Reset** (Occasional)
   - Keep certificates but reset other data
   - Useful for testing or troubleshooting
   ```bash
   podman volume rm logs user-data  # Remove specific volumes
   make volumes                     # Recreate removed volumes
   make pod-up                      # Start with mixed state
   ```

### Quick State Check
To determine your current state:
```bash
podman volume ls | grep -E "certs|logs|user-data"  # Check existing volumes
podman pod ps -a | grep podplay                    # Check pod status
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

## Troubleshooting and Logging

### Dual Logging Architecture
PodPlay uses a **dual logging approach** as detailed in `docs/specs/logging-architecture.md`:

1. **Container Runtime Logs** (stdout/stderr): Use `podman logs <container-name>`
2. **Persistent File Logs**: Stored in `/data/logs` volume for long-term analysis

### When Troubleshooting Mail or User Creation Issues:

**Always check BOTH log sources:**

```bash
# 1. Check container runtime logs first
podman logs podplay-mail --tail 20
podman logs podplay-apache --tail 20

# 2. Check persistent logs for detailed service information
podman exec podplay-mail ls -la /data/logs/mail/
podman exec podplay-mail tail -20 /data/logs/mail/postfix.log
podman exec podplay-mail tail -20 /data/logs/mail/auth.log

# 3. Check user management logs
podman exec podplay-mail tail -20 /data/logs/mail/user-manager.log
```

**Log Structure:**
```
/data/logs/
├── apache/          # Web server logs
│   ├── access.log   # HTTP requests
│   ├── error.log    # Apache errors
│   └── auth.log     # Authentication events
├── mail/            # Mail server logs  
│   ├── postfix.log  # SMTP operations
│   ├── dovecot.log  # IMAP/POP3 operations
│   └── auth.log     # Mail authentication
└── bind/            # DNS server logs
    └── general.log
```

**Key Points:**
- Container logs show immediate issues and startup problems
- Persistent logs provide detailed operational information
- Authentication and user creation issues often span multiple log files
- Always check both Apache and Mail logs for authentication workflows

## Implementation Guidelines

### CRITICAL: Always Rebuild Images Instead of Live File Copying

**Important Development Practice:**
- **ALWAYS** rebuild container images after making code changes
- **NEVER** copy modified files directly to running containers for testing
- Live file copying creates inconsistency between the built image and running container
- This leads to confusion about which version of code is actually deployed

**Correct Workflow:**
```bash
# After making code changes:
make clean           # Remove old images
make all             # Build new images with updated code
make pod-down        # Stop current pod
make pod-up          # Start with new images
```

**Why This Matters:**
- Ensures development environment matches production deployment
- Prevents issues where "working" code in containers doesn't persist after restart
- Maintains consistency between image builds and running services
- Avoids the problem of having multiple versions of files (e.g., `script.py` vs `script-working.py`)

### CRITICAL: Always Review Existing Architecture Before Implementation

Before implementing any technical specification:

1. **Architecture Discovery**
   - Read all Dockerfiles to understand base images and existing infrastructure
   - Check Makefiles to understand build/deployment workflows  
   - Review existing entrypoint scripts and their patterns
   - Identify existing volume mounts and data structures
   - Find existing configuration management (templates, scripts)

2. **Integration Requirements**
   - NEVER create standalone implementations that duplicate existing infrastructure
   - ALWAYS extend existing Dockerfiles rather than creating new ones
   - ALWAYS use existing base images (e.g., `base-debian:latest`)
   - ALWAYS follow existing group/user patterns (`certgroup`, `loggroup`)
   - ALWAYS use existing directory structures (`/data/src/`, `/data/logs/`)

3. **Component Extension Checklist**
   - [ ] Does this extend an existing service? Use its existing Dockerfile
   - [ ] Does this need new Python libraries? Add to existing venv setup
   - [ ] Does this need new Apache modules? Add to existing a2enmod
   - [ ] Does this need new volumes? Use existing volume structure
   - [ ] Does this need logging? Follow existing dual logging patterns
   - [ ] Does this need configuration? Extend existing entrypoint scripts

4. **File Organization**
   - Place new files in the implementation directory (`debian/`)
   - Follow existing naming conventions (e.g., `service-entrypoint.sh`)
   - Group related files logically within the implementation directory
   - Avoid creating parallel directory structures

5. **Before Starting Implementation**
   - Ask yourself: "What existing component does this extend?"
   - Identify the exact Dockerfile and entrypoint that need modification
   - Map new requirements to existing infrastructure patterns
   - Plan integration points before writing any code

**Example: Adding authentication to Apache**
- ✅ Extend `/debian/Dockerfile.apache` with CGI support
- ✅ Extend `/debian/apache-entrypoint.sh` with auth setup  
- ✅ Use existing `/data/user-data/` volume structure
- ✅ Follow existing logging patterns
- ❌ Create new `/apache/` directory with standalone Dockerfile