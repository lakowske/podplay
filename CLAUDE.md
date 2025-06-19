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