# Project Configuration

## User Settings
- **Domain**: lab.sethlakowske.com
- **Let's Encrypt Email**: lakowske@gmail.com

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