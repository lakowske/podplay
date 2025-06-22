# PodPlay Pod Deployment

This directory contains Podman Kubernetes YAML files for deploying the PodPlay service stack as pods.

## Quick Start

```bash
# Build all images
make all

# Deploy the complete stack
make deploy

# Or manually:
# 1. Initialize certificates
make pod-init
# 2. Wait for completion and cleanup
podman play kube --down pod-yaml/podplay-init-pod.yaml
# 3. Start services
make pod-up
```

## Files

- `podplay-init-pod.yaml` - Certificate initialization pod
- `podplay-pod.yaml` - Main services pod (Apache, BIND, Mail)
- `podplay-renewal-pod.yaml` - Certificate renewal pod

## Available Commands

```bash
make pod-up        # Start services pod
make pod-down      # Stop services pod
make pod-status    # Check pod status
make pod-logs      # View pod logs
make pod-renewal   # Run certificate renewal
```

## Configuration

Edit the YAML files to customize:
- Domain name
- Email address
- Certificate type (letsencrypt/self-signed)
- Port mappings
- Resource limits

Or use environment variables:
```bash
export PODPLAY_DOMAIN=mydomain.com
export PODPLAY_EMAIL=admin@mydomain.com
```

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