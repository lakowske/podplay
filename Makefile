.PHONY: build build-all build-base build-apache build-bind build-mail build-certbot clean help

build-all: build-apache build-bind build-mail build-certbot

build: build-base

build-base:
	podman build -t base:latest -f Dockerfile .

build-apache: build-base
	podman build -t podplay-apache:latest -f Dockerfile.apache .

build-bind: build-base
	podman build -t podplay-bind:latest -f Dockerfile.bind .

build-mail: build-base
	podman build -t podplay-mail:latest -f Dockerfile.mail .

build-certbot: build-base
	podman build -t podplay-certbot:latest -f Dockerfile.certbot .

clean:
	podman rmi podplay-apache:latest || true
	podman rmi podplay-bind:latest || true
	podman rmi podplay-mail:latest || true
	podman rmi podplay-certbot:latest || true
	podman rmi base:latest || true

help:
	@echo "Available targets:"
	@echo "  build-all    - Build all service images (depends on base)"
	@echo "  build        - Build base image (alias for build-base)"
	@echo "  build-base   - Build base Alpine image"
	@echo "  build-apache - Build Apache container image"
	@echo "  build-bind   - Build BIND DNS container image"
	@echo "  build-mail   - Build mail server container image"
	@echo "  build-certbot- Build Certbot container image"
	@echo "  clean        - Remove all built images"
	@echo "  help         - Show this help message"