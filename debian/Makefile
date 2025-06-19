.PHONY: all base apache bind mail certbot clean help

# Debian-specific targets
all: apache bind mail certbot

base:
	podman build -t base-debian:latest -f Dockerfile .

apache: base
	podman build -t podplay-apache-debian:latest -f Dockerfile.apache .

bind: base
	podman build -t podplay-bind-debian:latest -f Dockerfile.bind .

mail: base
	podman build -t podplay-mail-debian:latest -f Dockerfile.mail .

certbot: base
	podman build -t podplay-certbot-debian:latest -f Dockerfile.certbot .

clean:
	podman rmi podplay-apache-debian:latest || true
	podman rmi podplay-bind-debian:latest || true
	podman rmi podplay-mail-debian:latest || true
	podman rmi podplay-certbot-debian:latest || true
	podman rmi base-debian:latest || true

help:
	@echo "Debian Implementation Targets:"
	@echo "  all      - Build all Debian service images"
	@echo "  base     - Build base Debian image"
	@echo "  apache   - Build Debian Apache container"
	@echo "  bind     - Build Debian BIND DNS container"
	@echo "  mail     - Build Debian mail server container"
	@echo "  certbot  - Build Debian Certbot container"
	@echo "  clean    - Remove all Debian images"
	@echo "  help     - Show this help message"