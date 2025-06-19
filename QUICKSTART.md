# Quick Start Guide

## Build Images

Build all images with the Makefile:

```bash
make build-all
```

Or build specific images:
```bash
make build-base      # Base Alpine image (required first)
make build-certbot   # Certificate management
make build-apache    # Web server
make build-bind      # DNS server
make build-mail      # Mail server
```

## Create Certificate Volume

Create a named volume for SSL certificates:

```bash
podman volume create certs
```

## Generate SSL Certificates

### Self-signed certificates (for testing):
```bash
podman run --rm \
  -v certs:/data/certificates \
  -e DOMAIN=lab.sethlakowske.com \
  -e CERT_TYPE=self-signed \
  podplay-certbot:latest
```

### Let's Encrypt certificates (for production):
```bash
podman run --rm \
  -v certs:/data/certificates \
  -p 80:80 \
  -e DOMAIN=lab.sethlakowske.com \
  -e EMAIL=lakowske@gmail.com \
  -e CERT_TYPE=letsencrypt \
  -e STAGING=false \
  podplay-certbot:latest
```

The certificates will be stored in the `certs` volume and can be shared with other containers.

## Run Apache Web Server

Start the Apache container with SSL certificates:

```bash
podman run -d \
  --name apache-server \
  -v certs:/data/certificates \
  -p 8080:80 \
  -p 8443:443 \
  podplay-apache:latest
```

Access the web server at:
- HTTP: `http://localhost:8080`
- HTTPS: `https://localhost:8443`