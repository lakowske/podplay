# PodPlay Pod Deployment

This directory contains Podman Kubernetes YAML templates for deploying the PodPlay service stack as pods.

## Environment-Based Configuration

PodPlay now supports multiple deployment environments with automatic configuration generation.

### Quick Start

```bash
# Switch to your environment (lab or sethcore)
make env-switch ENV=sethcore  # For sethcore.com VPS
# OR
make env-switch ENV=lab       # For lab.sethlakowske.com home network

# Build all images
make all

# Deploy the complete stack
make pod-init         # Generate certificates
make pod-cert-cleanup # Clean up cert pod
make pod-up          # Start services
```

## Files

### Templates (in version control)
- `podplay-init-pod.yaml.template` - Certificate initialization pod template
- `podplay-pod.yaml.template` - Main services pod template (Apache, BIND, Mail)
- `podplay-renewal-pod.yaml.template` - Certificate renewal pod template

### Generated Files (git-ignored)
- `podplay-init-pod.yaml` - Generated from template with environment values
- `podplay-pod.yaml` - Generated from template with environment values
- `podplay-renewal-pod.yaml` - Generated from template with environment values

### Environment Files
- `.env.lab` - Configuration for lab.sethlakowske.com (home network)
- `.env.sethcore` - Configuration for sethcore.com (VPS)
- `.env` - Active configuration (copied from one of the above)

## Available Commands

```bash
make pod-up        # Start services pod
make pod-down      # Stop services pod
make pod-status    # Check pod status
make pod-logs      # View pod logs
make pod-renewal   # Run certificate renewal
```

## Configuration

### Switching Environments

```bash
# Check current environment
make env-check

# Switch to a different environment
make env-switch ENV=lab       # Home network deployment
make env-switch ENV=sethcore  # VPS deployment
```

### Creating New Environments

1. Create a new environment file: `.env.myenv`
2. Set all required variables (copy from `.env.lab` or `.env.sethcore` as template)
3. Switch to it: `make env-switch ENV=myenv`

### Environment Variables

Key configuration variables:
- `PODPLAY_DOMAIN` - Your domain name
- `PODPLAY_EMAIL` - Email for Let's Encrypt
- `PODPLAY_HOST_HTTP_PORT` - Host port for HTTP (80 or 8080)
- `PODPLAY_HOST_HTTPS_PORT` - Host port for HTTPS (443 or 8443)
- `PODPLAY_HOST_SMTP_PORT` - Host port for SMTP (25 or 2525)
- `PODPLAY_HOST_SUBMISSION_PORT` - Host port for mail submission (587 or 2587)
- `PODPLAY_HOST_IMAPS_PORT` - Host port for IMAPS (993 or 2993)
- `PODPLAY_CERT_TYPE` - Certificate type (letsencrypt/self-signed)
- `PODPLAY_STAGING` - Use Let's Encrypt staging (true/false)

## Troubleshooting

```bash
# Check pod details
podman pod inspect podplay

# Check individual container logs
podman logs podplay-apache
podman logs podplay-bind
podman logs podplay-mail

# Access container shell
podman exec -it podplay-apache /bin/bash
```