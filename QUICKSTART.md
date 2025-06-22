# PodPlay Quick Start Guide

## Overview

PodPlay provides a complete hosting stack with Apache, BIND DNS, Mail (Postfix/Dovecot), and automated certificate management using Debian containers.

## Quick Deployment (Recommended)

Deploy PodPlay using the step-by-step pod workflow:

```bash
# Navigate to the project
cd debian

# 1. Build all images
make all

# 2. Create volumes
make volumes

# 3. Generate certificates
make pod-init

# 4. Wait for completion, then clean up init pod
make pod-cert-cleanup

# 5. Start services
make pod-up
```

## Manual Deployment

### 1. Navigate to Project

```bash
# Navigate to the project directory
cd debian
```

### 2. Build Images

```bash
# Build all images
make all

# Or build individually
make base      # Base image (required first)
make apache    # Web server
make bind      # DNS server
make mail      # Mail server
make certbot   # Certificate management
```

### 3. Create Volumes

```bash
make volumes
```

This creates:
- `certs` - SSL/TLS certificates
- `logs` - Centralized logging

### 4. Generate Certificates

#### Option A: Let's Encrypt (Production)
```bash
podman run --rm --user root \
  -v certs:/data/certificates \
  -v logs:/data/logs \
  -p 8080:80 \
  -e CERT_TYPE=letsencrypt \
  -e DOMAIN=lab.sethlakowske.com \
  -e EMAIL=lakowske@gmail.com \
  -e STAGING=false \
  podplay-certbot-debian:latest
```

#### Option B: Self-Signed (Testing)
```bash
podman run --rm \
  -v certs:/data/certificates \
  -v logs:/data/logs \
  -e CERT_TYPE=self-signed \
  -e DOMAIN=lab.sethlakowske.com \
  podplay-certbot-debian:latest
```

### 5. Start Services

#### Using Pod (Recommended)
```bash
make pod-up
```

#### Individual Containers
```bash
# Apache Web Server
make run-apache DOMAIN=lab.sethlakowske.com

# BIND DNS Server
make run-bind DOMAIN=lab.sethlakowske.com

# Mail Server
make run-mail DOMAIN=lab.sethlakowske.com
```

## Accessing Services

- **Web**: 
  - HTTP: http://localhost:8080
  - HTTPS: https://localhost:8443
- **DNS**: Port 53
- **Mail**: 
  - SMTP: Port 25
  - Submission: Port 587
  - IMAPS: Port 993

## Management Commands

### Pod Management
```bash
make pod-status   # Check pod and container status
make pod-logs     # View pod logs
make pod-down     # Stop all services
make pod-renewal  # Renew certificates
```

### Individual Services
```bash
# View logs
podman logs apache  # or bind, mail

# Stop services
podman stop apache bind mail

# Remove services
podman rm apache bind mail
```

## Configuration

### Environment Variables

Create a `.env` file or export variables:
```bash
export PODPLAY_DOMAIN=mydomain.com
export PODPLAY_EMAIL=admin@mydomain.com
export PODPLAY_CERT_TYPE=letsencrypt  # or self-signed
```

### Network Configuration

If running behind a router:
- Forward external ports 80→8080 and 443→8443
- For Let's Encrypt, ensure port 80 is accessible from the internet

## Troubleshooting

### Check Service Status
```bash
make pod-status
# or
podman ps
```

### View Logs
```bash
# Pod logs
make pod-logs

# Individual service logs
podman logs podplay-apache
podman logs podplay-bind
podman logs podplay-mail

# Persistent logs
podman run --rm -v logs:/logs debian:12-slim cat /logs/apache/access.log
```

### Certificate Issues
```bash
# Check certificates
podman run --rm -v certs:/certs debian:12-slim ls -la /certs/

# Regenerate certificates
make pod-down
make pod-init
# Wait for completion, then:
make pod-up
```

### DNS Testing
```bash
# Test DNS resolution
dig @localhost lab.sethlakowske.com

# Or use the system resolver
nslookup lab.sethlakowske.com localhost
```

## Next Steps

- Read the full documentation in `/docs/specs/`
- Configure mail users and domains
- Set up DNS records for your domain
- Enable certificate auto-renewal with systemd or cron

## Quick Commands Reference

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
make pod-renewal      # Renew certificates
make clean           # Remove images
make help            # Show all options
```