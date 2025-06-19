.PHONY: build build-all build-base build-apache build-bind build-mail build-certbot clean help
.PHONY: alpine alpine-all alpine-base alpine-apache alpine-bind alpine-mail alpine-certbot alpine-clean
.PHONY: debian debian-all debian-base debian-apache debian-bind debian-mail debian-certbot debian-clean

# Default to Alpine for backward compatibility
build-all: alpine-all
build: alpine-base
build-base: alpine-base
build-apache: alpine-apache
build-bind: alpine-bind
build-mail: alpine-mail
build-certbot: alpine-certbot

# Alpine builds
alpine-all: alpine-apache alpine-bind alpine-mail alpine-certbot

alpine: alpine-base

alpine-base:
	podman build -t base:latest -f alpine/Dockerfile alpine/

alpine-apache: alpine-base
	podman build -t podplay-apache:latest -f alpine/Dockerfile.apache alpine/

alpine-bind: alpine-base
	podman build -t podplay-bind:latest -f alpine/Dockerfile.bind alpine/

alpine-mail: alpine-base
	podman build -t podplay-mail:latest -f alpine/Dockerfile.mail alpine/

alpine-certbot: alpine-base
	podman build -t podplay-certbot:latest -f alpine/Dockerfile.certbot alpine/

alpine-clean:
	podman rmi podplay-apache:latest || true
	podman rmi podplay-bind:latest || true
	podman rmi podplay-mail:latest || true
	podman rmi podplay-certbot:latest || true
	podman rmi base:latest || true

# Debian builds
debian-all: debian-apache debian-bind debian-mail debian-certbot

debian: debian-base

debian-base:
	podman build -t base-debian:latest -f debian/Dockerfile debian/

debian-apache: debian-base
	podman build -t podplay-apache-debian:latest -f debian/Dockerfile.apache debian/

debian-bind: debian-base
	podman build -t podplay-bind-debian:latest -f debian/Dockerfile.bind debian/

debian-mail: debian-base
	podman build -t podplay-mail-debian:latest -f debian/Dockerfile.mail debian/

debian-certbot: debian-base
	podman build -t podplay-certbot-debian:latest -f debian/Dockerfile.certbot debian/

debian-clean:
	podman rmi podplay-apache-debian:latest || true
	podman rmi podplay-bind-debian:latest || true
	podman rmi podplay-mail-debian:latest || true
	podman rmi podplay-certbot-debian:latest || true
	podman rmi base-debian:latest || true

# Clean all images
clean: alpine-clean debian-clean

help:
	@echo "Available targets:"
	@echo ""
	@echo "Alpine builds (default):"
	@echo "  build-all    - Build all Alpine service images (backward compatibility)"
	@echo "  alpine-all   - Build all Alpine service images"
	@echo "  alpine-base  - Build base Alpine image"
	@echo "  alpine-apache - Build Alpine Apache container"
	@echo "  alpine-bind  - Build Alpine BIND DNS container"
	@echo "  alpine-mail  - Build Alpine mail server container"
	@echo "  alpine-certbot - Build Alpine Certbot container"
	@echo "  alpine-clean - Remove all Alpine images"
	@echo ""
	@echo "Debian builds:"
	@echo "  debian-all   - Build all Debian service images"
	@echo "  debian-base  - Build base Debian image"
	@echo "  debian-apache - Build Debian Apache container"
	@echo "  debian-bind  - Build Debian BIND DNS container"
	@echo "  debian-mail  - Build Debian mail server container"
	@echo "  debian-certbot - Build Debian Certbot container"
	@echo "  debian-clean - Remove all Debian images"
	@echo ""
	@echo "General:"
	@echo "  clean        - Remove all built images (Alpine and Debian)"
	@echo "  help         - Show this help message"