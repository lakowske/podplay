# Podman Pod Composition Specification

## Overview

This specification defines the Podman pod composition for the PodPlay service stack, providing a declarative way to deploy all services together with proper volume sharing, networking, and service dependencies.

## Goals

1. Provide YAML files to deploy the entire PodPlay stack
2. Ensure proper volume sharing between services
3. Define service dependencies and startup order
4. Maintain security boundaries while enabling necessary inter-service communication
5. Support both development and production deployments

## Architecture

### Pod Structure

The PodPlay deployment consists of two pods:

1. **Init Pod** (podplay-init)
   - Certbot container for initial certificate generation
   - Runs once before main pod startup

2. **Service Pod** (podplay)
   - Apache container - Web server with SSL/TLS
   - BIND container - DNS server
   - Mail container - Postfix/Dovecot mail server

### Shared Resources

#### Volumes
- `certs` - SSL/TLS certificates (shared: apache, mail, certbot)
- `logs` - Centralized logging (shared: all services)

#### Network
- Pod network namespace for inter-container communication
- Published ports mapped to host

## Pod Definitions

### Init Pod (podplay-init-pod.yaml)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: podplay-init
  labels:
    app: podplay
    role: init
spec:
  restartPolicy: Never
  
  volumes:
    - name: certs
      persistentVolumeClaim:
        claimName: podplay-certs
    - name: logs
      persistentVolumeClaim:
        claimName: podplay-logs
  
  containers:
    - name: certbot
      image: localhost/podplay-certbot-debian:latest
      env:
        - name: CERT_TYPE
          value: "letsencrypt"  # or "self-signed"
        - name: DOMAIN
          value: "lab.sethlakowske.com"
        - name: EMAIL
          value: "lakowske@gmail.com"
        - name: STAGING
          value: "false"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
        - name: logs
          mountPath: /data/logs
      ports:
        - containerPort: 80
          hostPort: 8080
          protocol: TCP
      securityContext:
        runAsUser: 0  # Required for Let's Encrypt
```

### Service Pod (podplay-pod.yaml)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: podplay
  labels:
    app: podplay
    role: services
spec:
  hostname: podplay
  
  # Shared volumes
  volumes:
    - name: certs
      persistentVolumeClaim:
        claimName: podplay-certs
    - name: logs
      persistentVolumeClaim:
        claimName: podplay-logs
  
  # Service containers
  containers:
    # Apache Web Server
    - name: apache
      image: localhost/podplay-apache-debian:latest
      env:
        - name: DOMAIN
          value: "lab.sethlakowske.com"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
          readOnly: true
        - name: logs
          mountPath: /data/logs
      ports:
        - containerPort: 80
          hostPort: 8080
          protocol: TCP
        - containerPort: 443
          hostPort: 8443
          protocol: TCP
      livenessProbe:
        httpGet:
          path: /
          port: 80
        initialDelaySeconds: 30
        periodSeconds: 10
      readinessProbe:
        httpGet:
          path: /
          port: 80
        initialDelaySeconds: 5
        periodSeconds: 5
    
    # BIND DNS Server
    - name: bind
      image: localhost/podplay-bind-debian:latest
      env:
        - name: DOMAIN_NAME
          value: "lab.sethlakowske.com"
        - name: DOMAIN_IP
          value: "127.0.0.1"
        - name: DNS_FORWARDERS
          value: "8.8.8.8; 8.8.4.4; 1.1.1.1; 1.0.0.1"
      volumeMounts:
        - name: logs
          mountPath: /data/logs
      ports:
        - containerPort: 53
          hostPort: 53
          protocol: TCP
        - containerPort: 53
          hostPort: 53
          protocol: UDP
      livenessProbe:
        exec:
          command:
            - /usr/bin/dig
            - "@127.0.0.1"
            - "+short"
            - "lab.sethlakowske.com"
        initialDelaySeconds: 10
        periodSeconds: 30
    
    # Mail Server
    - name: mail
      image: localhost/podplay-mail-debian:latest
      env:
        - name: MAIL_DOMAIN
          value: "lab.sethlakowske.com"
        - name: MAIL_SERVER_NAME
          value: "mail.lab.sethlakowske.com"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
          readOnly: true
        - name: logs
          mountPath: /data/logs
      ports:
        - containerPort: 25
          hostPort: 25
          protocol: TCP
        - containerPort: 587
          hostPort: 587
          protocol: TCP
        - containerPort: 993
          hostPort: 993
          protocol: TCP
      livenessProbe:
        tcpSocket:
          port: 25
        initialDelaySeconds: 30
        periodSeconds: 10

  # Pod-level settings
  restartPolicy: Always
  dnsPolicy: ClusterFirst
```

### Certificate Renewal Pod (podplay-renewal-pod.yaml)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: podplay-renewal
  labels:
    app: podplay
    role: renewal
spec:
  restartPolicy: Never
  
  volumes:
    - name: certs
      persistentVolumeClaim:
        claimName: podplay-certs
    - name: logs
      persistentVolumeClaim:
        claimName: podplay-logs
  
  containers:
    - name: certbot
      image: localhost/podplay-certbot-debian:latest
      command: ["/usr/local/bin/certbot-entrypoint.sh", "renew"]
      env:
        - name: CERT_TYPE
          value: "letsencrypt"
        - name: DOMAIN
          value: "lab.sethlakowske.com"
        - name: EMAIL
          value: "lakowske@gmail.com"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
        - name: logs
          mountPath: /data/logs
      ports:
        - containerPort: 80
          hostPort: 8080
          protocol: TCP
      securityContext:
        runAsUser: 0
```

## Deployment Workflow

### Step-by-Step Deployment (Recommended)

The recommended approach uses explicit Make targets for each deployment step:

```bash
# Navigate to implementation directory
cd debian  # or cd alpine

# 1. Build all container images
make all

# 2. Create persistent volumes
make volumes

# 3. Generate SSL certificates
make pod-init

# 4. Monitor certificate generation
podman logs -f podplay-init-certbot

# 5. Clean up init pod when complete
make pod-cert-cleanup

# 6. Start main services
make pod-up

# 7. Verify deployment
make pod-status
```

This approach provides:
- **Transparency**: Each step is visible and controllable
- **Debugging**: Easy to identify and fix issues at any step
- **Flexibility**: Can repeat individual steps as needed
- **Education**: Operators understand what each step does

### Direct Podman Commands

For users who prefer direct podman commands without Make targets:

```bash
# 1. Create volumes
podman volume create podplay-certs
podman volume create podplay-logs

# 2. Generate certificates (Let's Encrypt)
podman play kube pod-yaml/podplay-init-pod.yaml

# 3. Monitor progress
podman logs -f podplay-init-certbot

# 4. Wait for completion and clean up
podman play kube --down pod-yaml/podplay-init-pod.yaml

# 5. Start services
podman play kube pod-yaml/podplay-pod.yaml

# 6. Check status
podman pod ps
podman ps --pod
```

**Note**: The Make targets are recommended as they provide better user experience with informative output and error handling.

### Using systemd

Create systemd services for automated startup:

`podplay-init.service`:
```ini
[Unit]
Description=PodPlay Certificate Initialization
Before=podplay.service
ConditionPathExists=!/var/lib/containers/storage/volumes/podplay-certs/_data/lab.sethlakowske.com

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/podman play kube %h/.config/podplay/podplay-init-pod.yaml
ExecStartPost=/bin/sleep 30
ExecStop=/usr/bin/podman play kube --down %h/.config/podplay/podplay-init-pod.yaml

[Install]
WantedBy=podplay.service
```

`podplay.service`:
```ini
[Unit]
Description=PodPlay Service Pod
After=network-online.target podplay-init.service
Wants=network-online.target
Requires=podplay-init.service

[Service]
Type=forking
Restart=on-failure
RestartSec=30s
ExecStartPre=/usr/bin/podman volume create podplay-certs
ExecStartPre=/usr/bin/podman volume create podplay-logs
ExecStart=/usr/bin/podman play kube %h/.config/podplay/podplay-pod.yaml
ExecStop=/usr/bin/podman play kube --down %h/.config/podplay/podplay-pod.yaml
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

`podplay-renewal.timer`:
```ini
[Unit]
Description=Weekly PodPlay certificate renewal
Requires=podplay-renewal.service

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
```

`podplay-renewal.service`:
```ini
[Unit]
Description=PodPlay certificate renewal
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/podman play kube %h/.config/podplay/podplay-renewal-pod.yaml
ExecStartPost=/bin/sleep 10
ExecStop=/usr/bin/podman play kube --down %h/.config/podplay/podplay-renewal-pod.yaml
```

## Configuration Management

### Environment-based Configuration

Create `podplay.env`:
```bash
# Domain configuration
PODPLAY_DOMAIN=lab.sethlakowske.com
PODPLAY_EMAIL=lakowske@gmail.com

# Certificate configuration
PODPLAY_CERT_TYPE=letsencrypt  # or self-signed
PODPLAY_STAGING=false

# DNS configuration
PODPLAY_DNS_FORWARDERS="8.8.8.8; 8.8.4.4; 1.1.1.1; 1.0.0.1"
PODPLAY_DOMAIN_IP=127.0.0.1

# Mail configuration
PODPLAY_MAIL_SERVER_NAME=mail.lab.sethlakowske.com
```

### Template Processing

For dynamic configuration, use template processing:

```bash
#!/bin/bash
# generate-pod-yaml.sh
envsubst < podplay-pod.yaml.template > podplay-pod.yaml
```

## Makefile Integration

The `debian/Makefile` includes these pod deployment targets:

```makefile
# Pod deployment targets
pod-init: volumes
	@echo "Starting certificate initialization pod..."
	@echo "This will generate SSL certificates for lab.sethlakowske.com"
	@echo "Port 8080 must be available for Let's Encrypt validation"
	podman play kube pod-yaml/podplay-init-pod.yaml
	@echo ""
	@echo "Certificate initialization started. Monitor with:"
	@echo "  podman logs -f podplay-init-certbot"
	@echo ""
	@echo "When complete, clean up with:"
	@echo "  make pod-cert-cleanup"

pod-cert-cleanup:
	@echo "Cleaning up certificate initialization pod..."
	podman play kube --down pod-yaml/podplay-init-pod.yaml || true
	@echo "Certificate pod removed. Ready to start services with:"
	@echo "  make pod-up"

pod-up: volumes
	@echo "Starting PodPlay services pod..."
	@echo "This will start Apache, BIND DNS, and Mail services"
	podman play kube pod-yaml/podplay-pod.yaml
	@echo ""
	@echo "Services starting. Check status with:"
	@echo "  make pod-status"

pod-down:
	@echo "Stopping PodPlay services..."
	podman play kube --down pod-yaml/podplay-pod.yaml || true

pod-status:
	@echo "PodPlay pod status:"
	@podman pod ps
	@echo ""
	@echo "Container status:"
	@podman ps --pod --format "table {{.Names}}\t{{.Pod}}\t{{.Status}}"

pod-logs:
	@echo "Showing PodPlay pod logs..."
	podman pod logs -f podplay

pod-renewal: volumes
	@echo "Running certificate renewal pod..."
	@echo "This will attempt to renew existing Let's Encrypt certificates"
	podman play kube pod-yaml/podplay-renewal-pod.yaml
```

### Workflow Commands

The help output shows the recommended workflow:

```bash
Pod Deployment Workflow:
  1. make all           - Build all container images
  2. make volumes       - Create required volumes
  3. make pod-init      - Generate SSL certificates
  4. make pod-cert-cleanup - Clean up certificate pod
  5. make pod-up        - Start PodPlay services

Pod Management:
  pod-status    - Show pod and container status
  pod-logs      - Follow pod logs
  pod-down      - Stop PodPlay services pod
  pod-renewal   - Run certificate renewal
```

## Troubleshooting

### Common Issues

1. **Port conflicts during init**
   - Ensure no services are using port 8080 during certificate generation
   - Use `podman pod stop podplay` before running init

2. **Volume permissions**
   - Init container runs as root for Let's Encrypt
   - Service containers use appropriate users with group permissions

3. **Certificate renewal failures**
   - Check that port 8080 is available
   - Verify DNS is resolving correctly
   - Review logs in the logs volume

### Debug Commands

```bash
# Check pod status
podman pod inspect podplay

# View container logs
podman logs podplay-apache

# Execute commands in running container
podman exec -it podplay-apache /bin/bash

# Check volume contents
podman volume inspect podplay-certs
podman run --rm -v podplay-certs:/data:ro alpine ls -la /data
```

## Security Considerations

1. **Init Pod Security**
   - Runs as root only when necessary (Let's Encrypt)
   - Minimal attack surface - exits after completion

2. **Service Pod Security**
   - Services run as non-root where possible
   - Read-only certificate mounts for services
   - SELinux labels on volumes

3. **Network Security**
   - Consider firewall rules for exposed ports
   - Use pod network isolation where appropriate

## Future Enhancements

1. **Kubernetes Compatibility**
   - Full Kubernetes manifest support
   - Helm chart creation

2. **Advanced Orchestration**
   - Health check dependencies
   - Graceful shutdown ordering

3. **Monitoring Integration**
   - Prometheus metrics
   - Grafana dashboards

## References

- [Podman Play Kube](https://docs.podman.io/en/latest/markdown/podman-play-kube.1.html)
- [Podman Pod](https://docs.podman.io/en/latest/markdown/podman-pod.1.html)
- Service specifications in `/docs/specs/`