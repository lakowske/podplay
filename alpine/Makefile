.PHONY: all base apache bind mail certbot clean help

# Alpine-specific targets
all: apache bind mail certbot

base:
	podman build -t base:latest -f Dockerfile .

apache: base
	podman build -t podplay-apache:latest -f Dockerfile.apache .

bind: base
	podman build -t podplay-bind:latest -f Dockerfile.bind .

mail: base
	podman build -t podplay-mail:latest -f Dockerfile.mail .

certbot: base
	podman build -t podplay-certbot:latest -f Dockerfile.certbot .

clean:
	podman rmi podplay-apache:latest || true
	podman rmi podplay-bind:latest || true
	podman rmi podplay-mail:latest || true
	podman rmi podplay-certbot:latest || true
	podman rmi base:latest || true

help:
	@echo "Alpine Implementation Targets:"
	@echo "  all      - Build all Alpine service images"
	@echo "  base     - Build base Alpine image"
	@echo "  apache   - Build Alpine Apache container"
	@echo "  bind     - Build Alpine BIND DNS container"
	@echo "  mail     - Build Alpine mail server container"
	@echo "  certbot  - Build Alpine Certbot container"
	@echo "  clean    - Remove all Alpine images"
	@echo "  help     - Show this help message"