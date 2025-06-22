# Build System Specification

## Purpose
Define the build system architecture, conventions, and automation for container image management.

## Scope
- Makefile structure and targets
- Docker/Podman build patterns
- Image tagging and versioning
- Dependency management
- CI/CD integration

## Requirements

### Functional Requirements
1. Hierarchical build system with base image dependencies
2. Consistent image tagging and naming conventions
3. Build caching and optimization
4. Clean-up and maintenance targets
5. Cross-platform compatibility

### Non-Functional Requirements
1. Fast incremental builds
2. Minimal build context
3. Clear build output and error messages
4. Reproducible builds
5. Small final image sizes

## Build System Architecture

### Directory Structure
```
podplay/
├── debian/
│   ├── Makefile
│   ├── Dockerfile (base)
│   ├── Dockerfile.apache
│   ├── Dockerfile.bind
│   ├── Dockerfile.mail
│   └── Dockerfile.certbot
├── src/
│   └── cert_manager.py
├── requirements.txt
└── Makefile (root)
```

### Makefile Hierarchy
```makefile
# Root Makefile
.PHONY: all debian clean help

all: debian

debian:
	$(MAKE) -C debian all

clean:
	$(MAKE) -C debian clean
```

## Image Naming Conventions

### Naming Pattern
```
<service>-<distribution>:<version>
podplay-<service>-<distribution>:<version>
```

### Examples
```
base-debian:latest
podplay-apache-debian:latest
podplay-apache-debian:v1.0.0
```

### Image Registry
```
localhost/<image>:latest          # Local development
registry.local/<image>:latest     # Private registry
ghcr.io/username/<image>:latest   # GitHub Container Registry
```

## Debian Implementation

### Makefile Structure
```makefile
.PHONY: all base apache bind mail certbot clean help

# Version management
VERSION ?= latest
REGISTRY ?= localhost

# Image names
BASE_IMAGE = base-debian:$(VERSION)
APACHE_IMAGE = podplay-apache-debian:$(VERSION)
BIND_IMAGE = podplay-bind-debian:$(VERSION)
MAIL_IMAGE = podplay-mail-debian:$(VERSION)
CERTBOT_IMAGE = podplay-certbot-debian:$(VERSION)

# Build all services
all: apache bind mail certbot

# Base image (prerequisite for all services)
base:
	@echo "Building base Debian image..."
	podman build -t $(BASE_IMAGE) -f debian/Dockerfile ..
	@echo "Base image built: $(BASE_IMAGE)"

# Service images with base dependency
apache: base
	@echo "Building Apache service..."
	podman build -t $(APACHE_IMAGE) -f debian/Dockerfile.apache ..
	@echo "Apache image built: $(APACHE_IMAGE)"

bind: base
	@echo "Building BIND DNS service..."
	podman build -t $(BIND_IMAGE) -f debian/Dockerfile.bind ..
	@echo "BIND image built: $(BIND_IMAGE)"

mail: base
	@echo "Building Mail service..."
	podman build -t $(MAIL_IMAGE) -f debian/Dockerfile.mail ..
	@echo "Mail image built: $(MAIL_IMAGE)"

certbot: base
	@echo "Building Certbot service..."
	podman build -t $(CERTBOT_IMAGE) -f debian/Dockerfile.certbot ..
	@echo "Certbot image built: $(CERTBOT_IMAGE)"

# Clean up images
clean:
	-podman rmi $(APACHE_IMAGE) 2>/dev/null
	-podman rmi $(BIND_IMAGE) 2>/dev/null
	-podman rmi $(MAIL_IMAGE) 2>/dev/null
	-podman rmi $(CERTBOT_IMAGE) 2>/dev/null
	-podman rmi $(BASE_IMAGE) 2>/dev/null
	@echo "Images cleaned up"

# Help target
help:
	@echo "Debian Implementation Build Targets:"
	@echo "  all      - Build all service images"
	@echo "  base     - Build base Debian image"
	@echo "  apache   - Build Apache web server"
	@echo "  bind     - Build BIND DNS server"
	@echo "  mail     - Build mail server (Postfix/Dovecot)"
	@echo "  certbot  - Build certificate generation service"
	@echo "  clean    - Remove all built images"
	@echo "  help     - Show this help message"
	@echo ""
	@echo "Variables:"
	@echo "  VERSION  - Image version tag (default: latest)"
	@echo "  REGISTRY - Container registry (default: localhost)"
```

## Build Context Optimization

### .dockerignore Pattern
```
# .dockerignore
.git/
.github/
docs/
*.md
README.md
LICENSE
.gitignore
**/.DS_Store
**/Thumbs.db
**/.vscode/
**/.idea/

# Keep only necessary files
!src/
!requirements.txt
!debian/
```

### Multi-Stage Build Pattern
```dockerfile
# Build stage
FROM debian:bookworm-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Build application
COPY src/ /build/src/
WORKDIR /build
RUN make build

# Runtime stage
FROM debian:bookworm-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Copy built artifacts
COPY --from=builder /build/dist/ /app/

# Runtime configuration
WORKDIR /app
ENTRYPOINT ["./app"]
```

## Build Automation

### GitHub Actions Workflow
```yaml
name: Build Container Images

on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    strategy:
      matrix:
        distro: [debian]
        service: [apache, bind, mail, certbot]

    steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Setup Podman
      run: |
        sudo apt-get update
        sudo apt-get install -y podman

    - name: Log in to Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-${{ matrix.service }}-${{ matrix.distro }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}

    - name: Build base image
      run: |
        cd ${{ matrix.distro }}
        make base

    - name: Build service image
      run: |
        cd ${{ matrix.distro }}
        make ${{ matrix.service }}

    - name: Push image
      run: |
        podman tag podplay-${{ matrix.service }}-${{ matrix.distro }}:latest \
          ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-${{ matrix.service }}-${{ matrix.distro }}:${{ github.sha }}
        podman push ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-${{ matrix.service }}-${{ matrix.distro }}:${{ github.sha }}
```

### Local Development Workflow
```bash
#!/bin/bash
# dev-build.sh

set -e

SERVICES="apache bind mail certbot"
DISTRO="debian"

echo "Starting development build..."

# Build base image
echo "Building base image..."
cd $DISTRO
make base

# Build services in parallel
echo "Building services..."
for service in $SERVICES; do
    echo "Building $service..."
    make $service &
done

# Wait for all builds to complete
wait

echo "All builds completed successfully!"
```

## Build Caching

### Layer Caching Strategy
```dockerfile
# Cache package installation separately from app code
FROM debian:bookworm-slim

# 1. Install system packages (changes rarely)
RUN apt-get update && apt-get install -y --no-install-recommends \
    package1 package2 package3 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies (changes occasionally)
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

# 3. Copy application code (changes frequently)
COPY src/ /app/src/

# 4. Set up runtime
WORKDIR /app
ENTRYPOINT ["python", "src/app.py"]
```

### Build Cache Management
```makefile
# Clear build cache
clean-cache:
	podman system prune -f
	podman volume prune -f

# Deep clean (remove all images)
clean-all:
	podman system prune -a -f
	podman volume prune -f
```

## Testing Integration

### Build Testing
```makefile
# Test builds
test: all
	@echo "Testing built images..."
	@for image in $(APACHE_IMAGE) $(BIND_IMAGE) $(MAIL_IMAGE) $(CERTBOT_IMAGE); do \
		echo "Testing $$image..."; \
		podman run --rm $$image --help > /dev/null || exit 1; \
	done
	@echo "All image tests passed!"

# Security scanning
security-scan: all
	@echo "Running security scans..."
	@for image in $(APACHE_IMAGE) $(BIND_IMAGE) $(MAIL_IMAGE) $(CERTBOT_IMAGE); do \
		echo "Scanning $$image..."; \
		podman run --rm -v /var/run/docker.sock:/var/run/docker.sock \
			aquasec/trivy image $$image; \
	done
```

### Container Health Checks
```dockerfile
# Add health check to Dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1
```

## Version Management

### Semantic Versioning
```bash
# Version tagging
VERSION_MAJOR=1
VERSION_MINOR=0
VERSION_PATCH=0
VERSION_BUILD=$(shell git rev-parse --short HEAD)

VERSION_TAG=v$(VERSION_MAJOR).$(VERSION_MINOR).$(VERSION_PATCH)
VERSION_FULL=$(VERSION_TAG)-$(VERSION_BUILD)
```

### Release Process
```makefile
# Tag and push release
release: all
	@echo "Creating release $(VERSION_TAG)..."
	@for image in $(APACHE_IMAGE) $(BIND_IMAGE) $(MAIL_IMAGE) $(CERTBOT_IMAGE); do \
		podman tag $$image $${image%:*}:$(VERSION_TAG); \
		podman push $${image%:*}:$(VERSION_TAG); \
	done
	git tag $(VERSION_TAG)
	git push origin $(VERSION_TAG)
```

## Cross-Platform Builds

### Multi-Architecture Support
```makefile
# Build for multiple architectures
build-multiarch:
	podman buildx build \
		--platform linux/amd64,linux/arm64,linux/arm/v7 \
		--push \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION) \
		-f Dockerfile .
```

### Platform-Specific Optimization
```dockerfile
# Use platform-specific base images
FROM --platform=$BUILDPLATFORM debian:bookworm-slim AS builder
FROM --platform=$TARGETPLATFORM debian:bookworm-slim

# Architecture-specific package selection
RUN case "$TARGETARCH" in \
    amd64) apt-get install -y package-amd64 ;; \
    arm64) apt-get install -y package-arm64 ;; \
    armv7) apt-get install -y package-armv7 ;; \
    esac
```

## Documentation

### Build Documentation
```makefile
# Generate build documentation
docs:
	@echo "Generating build documentation..."
	@echo "# Build Information" > BUILD_INFO.md
	@echo "Generated: $(shell date)" >> BUILD_INFO.md
	@echo "" >> BUILD_INFO.md
	@echo "## Images Built" >> BUILD_INFO.md
	@podman images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.Created}}" \
		| grep podplay >> BUILD_INFO.md
```

## Future Enhancements

1. **Advanced Build Features**
   - BuildKit integration
   - Remote build caching
   - Distributed builds
   - Build secrets management

2. **Quality Assurance**
   - Automated vulnerability scanning
   - Performance benchmarking
   - Image size optimization
   - Compliance checking

3. **DevOps Integration**
   - ArgoCD integration
   - Helm chart generation
   - Kubernetes manifests
   - GitOps workflows