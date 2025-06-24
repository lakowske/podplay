# Service Bootstrap and Selection Specification

## Purpose
Define a flexible service deployment system that allows selective deployment of PodPlay services (Apache, BIND, Mail, Certbot) using individual pod templates and intelligent bootstrapping.

## Scope
- Individual pod templates per service
- Service selection via environment configuration
- Bootstrap initialization for shared resources
- Service dependency management
- Per-service volume and permission requirements
- Conditional certificate management

## Requirements

### Functional Requirements
1. Deploy individual services independently or in combination
2. Bootstrap shared UIDs/GIDs and volumes before service deployment
3. Handle service dependencies automatically
4. Support conditional certificate generation
5. Provide health checks and readiness probes per service
6. Enable service-specific port and volume configuration

### Non-Functional Requirements
1. Maintain consistency with existing pod composition patterns
2. Minimize resource usage for single-service deployments
3. Support rapid service scaling and replacement
4. Provide clear separation of concerns between services
5. Enable development and production deployment flexibility

## Design

### Service Architecture

#### Individual Service Pods
Replace monolithic pod with individual service pods:

```
pod-yaml/
├── podplay-apache-pod.yaml.template    # Web server only
├── podplay-bind-pod.yaml.template      # DNS server only  
├── podplay-mail-pod.yaml.template      # Mail server only
├── podplay-certbot-pod.yaml.template   # Certificate management
└── podplay-bootstrap-pod.yaml.template # Initialization
```

#### Service Selection Configuration
```bash
# .env service selection examples

# Full stack deployment (current behavior)
PODPLAY_SERVICES="apache,bind,mail"

# Web-only deployment
PODPLAY_SERVICES="apache"

# Mail-only deployment  
PODPLAY_SERVICES="mail"

# DNS-only deployment
PODPLAY_SERVICES="bind"

# Custom combinations
PODPLAY_SERVICES="apache,mail"  # Web + Mail (no local DNS)
```

### Individual Pod Templates

#### Apache Service Pod
```yaml
# podplay-apache-pod.yaml.template
apiVersion: v1
kind: Pod
metadata:
  name: podplay-apache
  labels:
    app: podplay
    service: apache
spec:
  hostname: podplay-apache
  
  volumes:
    - name: certs
      persistentVolumeClaim:
        claimName: ${PODPLAY_CERTS_VOLUME}
    - name: logs
      persistentVolumeClaim:
        claimName: ${PODPLAY_LOGS_VOLUME}
    - name: user-data
      persistentVolumeClaim:
        claimName: ${PODPLAY_USER_DATA_VOLUME}
  
  containers:
    - name: apache
      image: localhost/podplay-apache-debian:latest
      env:
        - name: DOMAIN
          value: "${PODPLAY_DOMAIN}"
        - name: SERVICES
          value: "${PODPLAY_SERVICES}"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
          readOnly: true
        - name: logs
          mountPath: /data/logs
        - name: user-data
          mountPath: /data/user-data
      ports:
        - containerPort: ${PODPLAY_CONTAINER_HTTP_PORT}
          hostPort: ${PODPLAY_HOST_HTTP_PORT}
          protocol: TCP
        - containerPort: ${PODPLAY_CONTAINER_HTTPS_PORT}
          hostPort: ${PODPLAY_HOST_HTTPS_PORT}
          protocol: TCP
      livenessProbe:
        httpGet:
          path: /health
          port: ${PODPLAY_CONTAINER_HTTP_PORT}
        initialDelaySeconds: 30
        periodSeconds: 10
      readinessProbe:
        httpGet:
          path: /ready
          port: ${PODPLAY_CONTAINER_HTTP_PORT}
        initialDelaySeconds: 5
        periodSeconds: 5
  
  restartPolicy: Always
```

#### Mail Service Pod
```yaml
# podplay-mail-pod.yaml.template
apiVersion: v1
kind: Pod
metadata:
  name: podplay-mail
  labels:
    app: podplay
    service: mail
spec:
  hostname: podplay-mail
  
  volumes:
    - name: certs
      persistentVolumeClaim:
        claimName: ${PODPLAY_CERTS_VOLUME}
    - name: logs
      persistentVolumeClaim:
        claimName: ${PODPLAY_LOGS_VOLUME}
    - name: user-data
      persistentVolumeClaim:
        claimName: ${PODPLAY_USER_DATA_VOLUME}
  
  containers:
    - name: mail
      image: localhost/podplay-mail-debian:latest
      env:
        - name: MAIL_DOMAIN
          value: "${PODPLAY_DOMAIN}"
        - name: MAIL_SERVER_NAME
          value: "${PODPLAY_MAIL_SERVER_NAME}"
        - name: SERVICES
          value: "${PODPLAY_SERVICES}"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
          readOnly: true
        - name: logs
          mountPath: /data/logs
        - name: user-data
          mountPath: /data/user-data
      ports:
        - containerPort: 25
          hostPort: ${PODPLAY_HOST_SMTP_PORT}
          protocol: TCP
        - containerPort: 587
          hostPort: ${PODPLAY_HOST_SUBMISSION_PORT}
          protocol: TCP
        - containerPort: 993
          hostPort: ${PODPLAY_HOST_IMAPS_PORT}
          protocol: TCP
      livenessProbe:
        tcpSocket:
          port: 25
        initialDelaySeconds: 30
        periodSeconds: 10
      readinessProbe:
        exec:
          command: ["/data/src/health_check.py", "--service", "mail"]
        initialDelaySeconds: 10
        periodSeconds: 30
  
  restartPolicy: Always
```

#### BIND Service Pod
```yaml
# podplay-bind-pod.yaml.template
apiVersion: v1
kind: Pod
metadata:
  name: podplay-bind
  labels:
    app: podplay
    service: bind
spec:
  hostname: podplay-bind
  
  volumes:
    - name: logs
      persistentVolumeClaim:
        claimName: ${PODPLAY_LOGS_VOLUME}
    - name: environments
      persistentVolumeClaim:
        claimName: ${PODPLAY_ENVIRONMENTS_VOLUME}
  
  containers:
    - name: bind
      image: localhost/podplay-bind-debian:latest
      env:
        - name: DOMAIN_NAME
          value: "${PODPLAY_DOMAIN}"
        - name: DOMAIN_IP
          value: "${PODPLAY_DOMAIN_IP}"
        - name: DNS_FORWARDERS
          value: "${PODPLAY_DNS_FORWARDERS}"
        - name: SERVICES
          value: "${PODPLAY_SERVICES}"
      volumeMounts:
        - name: logs
          mountPath: /data/logs
        - name: environments
          mountPath: /data/environments
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
            - "${PODPLAY_DOMAIN}"
        initialDelaySeconds: 10
        periodSeconds: 30
      readinessProbe:
        tcpSocket:
          port: 53
        initialDelaySeconds: 5
        periodSeconds: 5
  
  restartPolicy: Always
```

### Bootstrap Process

#### Bootstrap Pod Template
```yaml
# podplay-bootstrap-pod.yaml.template
apiVersion: v1
kind: Pod
metadata:
  name: podplay-bootstrap
  labels:
    app: podplay
    role: bootstrap
spec:
  restartPolicy: Never
  
  volumes:
    - name: certs
      persistentVolumeClaim:
        claimName: ${PODPLAY_CERTS_VOLUME}
    - name: logs
      persistentVolumeClaim:
        claimName: ${PODPLAY_LOGS_VOLUME}
    - name: user-data
      persistentVolumeClaim:
        claimName: ${PODPLAY_USER_DATA_VOLUME}
    - name: environments
      persistentVolumeClaim:
        claimName: ${PODPLAY_ENVIRONMENTS_VOLUME}
  
  containers:
    - name: bootstrap
      image: localhost/podplay-bootstrap:latest
      env:
        - name: SERVICES
          value: "${PODPLAY_SERVICES}"
        - name: DOMAIN
          value: "${PODPLAY_DOMAIN}"
        - name: ENV_NAME
          value: "${PODPLAY_ENV_NAME}"
      volumeMounts:
        - name: certs
          mountPath: /data/certificates
        - name: logs
          mountPath: /data/logs
        - name: user-data
          mountPath: /data/user-data
        - name: environments
          mountPath: /data/environments
      command: ["/data/src/bootstrap.py"]
      args: ["--validate", "--setup-permissions", "--generate-configs"]
```

#### Bootstrap Script
```python
#!/usr/bin/env python3
# /data/src/bootstrap.py

import os
import subprocess
import logging
from pathlib import Path

class PodPlayBootstrap:
    """Bootstrap PodPlay environment and services"""
    
    def __init__(self):
        self.services = os.environ.get('SERVICES', '').split(',')
        self.domain = os.environ.get('DOMAIN')
        self.env_name = os.environ.get('ENV_NAME')
        
    def validate_environment(self):
        """Validate environment configuration"""
        # Check required environment variables
        # Validate service combinations
        # Check volume accessibility
        
    def setup_shared_permissions(self):
        """Setup shared UIDs/GIDs across volumes"""
        # Ensure certgroup (9999) exists in all volumes
        # Ensure loggroup (9998) exists in all volumes  
        # Set proper ownership for shared directories
        
    def initialize_service_configs(self):
        """Generate initial service configurations"""
        for service in self.services:
            if service == 'apache':
                self.init_apache_config()
            elif service == 'mail':
                self.init_mail_config()
            elif service == 'bind':
                self.init_bind_config()
                
    def register_environment(self):
        """Register this environment with central management"""
        # Update environments.yaml if environments volume available
        # Register with central DNS if configured
```

### Service Dependencies

#### Dependency Matrix
```yaml
# Service dependency configuration
dependencies:
  apache:
    requires_volumes: [certs, logs, user-data]
    requires_groups: [certgroup, loggroup]
    requires_certificate: true
    health_endpoint: "/health"
    
  mail:
    requires_volumes: [certs, logs, user-data]
    requires_groups: [certgroup, loggroup]
    requires_certificate: true
    health_check: "smtp_ready"
    
  bind:
    requires_volumes: [logs, environments]
    requires_groups: [loggroup]
    requires_certificate: false
    health_check: "dns_query"
    
  certbot:
    requires_volumes: [certs, logs]
    requires_groups: [certgroup, loggroup]
    provides_certificate: true
    run_mode: "init_only"
```

### Enhanced Makefile Integration

#### New Service Management Targets
```makefile
# Service-specific deployment targets
pod-apache:
    @$(MAKE) env-check
    @$(MAKE) pod-bootstrap
    @if $(MAKE) requires-certs apache; then $(MAKE) pod-certbot; fi
    podman play kube pod-yaml/podplay-apache-pod.yaml

pod-mail:
    @$(MAKE) env-check  
    @$(MAKE) pod-bootstrap
    @if $(MAKE) requires-certs mail; then $(MAKE) pod-certbot; fi
    podman play kube pod-yaml/podplay-mail-pod.yaml

pod-bind:
    @$(MAKE) env-check
    @$(MAKE) pod-bootstrap
    podman play kube pod-yaml/podplay-bind-pod.yaml

# Deploy all configured services
pod-up-services: pod-bootstrap
    @echo "Deploying services: ${PODPLAY_SERVICES}"
    @for service in $(shell echo ${PODPLAY_SERVICES} | tr ',' ' '); do \
        echo "Deploying $$service..."; \
        $(MAKE) pod-$$service || exit 1; \
    done

# Stop all service pods
pod-down-services:
    @for service in apache mail bind; do \
        if podman pod exists podplay-$$service 2>/dev/null; then \
            echo "Stopping $$service..."; \
            podman play kube --down pod-yaml/podplay-$$service-pod.yaml || true; \
        fi; \
    done

# Health check for all running services
pod-health:
    @echo "Checking service health..."
    @for service in apache mail bind; do \
        if podman pod exists podplay-$$service 2>/dev/null; then \
            echo "$$service: $$(podman healthcheck run podplay-$$service-$$service 2>/dev/null || echo 'No healthcheck')"; \
        fi; \
    done
```

#### Service Detection Functions
```makefile
# Helper functions for service management
requires-certs:
    @case "$1" in \
        apache|mail) exit 0 ;; \
        *) exit 1 ;; \
    esac

service-enabled:
    @echo "${PODPLAY_SERVICES}" | grep -q "$1"

get-service-pod:
    @echo "podplay-$1"
```

## Implementation Guidelines

### Migration Strategy
1. Create individual pod templates alongside existing monolithic template
2. Add bootstrap pod and initialization scripts
3. Extend Makefile with new service-specific targets
4. Test individual service deployment
5. Deprecate monolithic pod template

### Volume Management
```bash
# Standard volumes for all deployments
STANDARD_VOLUMES="certs logs user-data"

# Additional volumes for specific services
BIND_VOLUMES="environments"

# Volume creation based on services
volumes-for-services:
    @for vol in ${STANDARD_VOLUMES}; do \
        podman volume create $$vol || true; \
    done
    @if echo "${PODPLAY_SERVICES}" | grep -q bind; then \
        podman volume create environments || true; \
    fi
```

### Health Check Implementation
```python
# /data/src/health_check.py
class ServiceHealthCheck:
    """Service-specific health checks"""
    
    def check_apache(self):
        """Check Apache health"""
        # HTTP request to /health endpoint
        # Check certificate validity
        # Verify configuration syntax
        
    def check_mail(self):
        """Check mail service health"""
        # Test SMTP connection
        # Check Dovecot status
        # Verify user authentication
        
    def check_bind(self):
        """Check DNS service health"""
        # Test DNS resolution
        # Check zone file validity
        # Verify forwarder connectivity
```

## Testing Strategy

### Unit Tests
- Individual pod template validation
- Service dependency resolution
- Bootstrap permission setup
- Health check implementations

### Integration Tests
- Single service deployment
- Multi-service combinations
- Service communication
- Volume sharing between services

### Performance Tests
- Resource usage per service
- Startup time comparisons
- Memory footprint analysis
- Network performance impact

## Future Enhancements

1. **Auto-scaling**
   - Horizontal pod autoscaler integration
   - Load-based service scaling
   - Automatic failover between services

2. **Service Mesh**
   - Istio integration for service communication
   - mTLS between services
   - Traffic management and observability

3. **Blue-Green Deployment**
   - Zero-downtime service updates
   - Automatic rollback on failure
   - Canary deployment support