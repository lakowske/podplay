# Certificate Management System

This document explains how the certificate management system works across all containers.

## Certificate User and Group

All containers include a dedicated user and group for certificate access:
- **User**: certuser (UID 9999)
- **Group**: certgroup (GID 9999)

## How It Works

1. The `certbot-crypto` container generates certificates as the `certuser`
2. Certificates are stored with these permissions:
   - Public certificates (fullchain.pem): 644 (world-readable)
   - Private keys (privkey.pem): 640 (owner and group readable)
3. Service containers have their users added to `certgroup` for access

## Container-Specific Users in certgroup

- **Apache**: apache user
- **Mail**: postfix, dovecot, dovenull users  
- **Bind**: named user

## Usage Examples

### Generate Self-Signed Certificate
```bash
# Create a volume for certificates
podman volume create certificates

# Generate self-signed certificate
podman run --rm -v certificates:/data/certificates certbot-crypto
```

### Generate Let's Encrypt Certificate
```bash
podman run --rm -v certificates:/data/certificates \
  -e CERT_TYPE=letsencrypt \
  -e DOMAIN=example.com \
  -e EMAIL=admin@example.com \
  -e STAGING=false \
  certbot-crypto
```

### Use Certificates in Apache
```bash
# Apache can read certificates because apache user is in certgroup
podman run -v certificates:/data/certificates:ro apache

# In Apache config, reference:
# SSLCertificateFile /data/certificates/fullchain.pem
# SSLCertificateKeyFile /data/certificates/privkey.pem
```

### Use Certificates in Mail Services
```bash
# Postfix and Dovecot can read certificates
podman run -v certificates:/data/certificates:ro mail

# In Postfix/Dovecot config, reference the certificate paths
```

## Verifying Access

To verify a container can access certificates:

```bash
# Run container and check certificate permissions
podman run -v certificates:/data/certificates:ro apache \
  ls -la /data/certificates/

# Check group membership
podman run apache id apache
```

## Troubleshooting

1. **Permission Denied**: Ensure the service user is in certgroup
2. **Missing Certificates**: Check the certbot-crypto container logs
3. **Wrong Ownership**: Certificates should be owned by certuser:certgroup

## Security Notes

- Private keys are only readable by certuser and certgroup members
- Never make private keys world-readable
- Use read-only mounts (`:ro`) for service containers
- The certuser has no shell and cannot be used for login