.PHONY: all base apache bind mail certbot clean help volumes clean-volumes test-logging run-examples

# Debian-specific targets
all: apache bind mail certbot

base:
	podman build -t base-debian:latest -f debian/Dockerfile ..

apache: base
	podman build -t podplay-apache-debian:latest -f debian/Dockerfile.apache ..

bind: base
	podman build -t podplay-bind-debian:latest -f debian/Dockerfile.bind ..

mail: base
	podman build -t podplay-mail-debian:latest -f debian/Dockerfile.mail ..

certbot: base
	podman build -t podplay-certbot-debian:latest -f debian/Dockerfile.certbot ..

# Volume management
volumes:
	@echo "Creating Podplay volumes..."
	podman volume create certs || true
	podman volume create logs || true
	@echo "Volumes created:"
	@echo "  - certs: /data/certificates (certificate storage)"
	@echo "  - logs:  /data/logs (persistent logging)"

clean-volumes:
	@echo "Warning: This will remove all Podplay volumes and their data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		podman volume rm logs || true; \
		podman volume rm certs || true; \
		echo "Volumes removed"; \
	else \
		echo "Operation cancelled"; \
	fi

clean:
	podman rmi podplay-apache-debian:latest || true
	podman rmi podplay-bind-debian:latest || true
	podman rmi podplay-mail-debian:latest || true
	podman rmi podplay-certbot-debian:latest || true
	podman rmi base-debian:latest || true

# Testing and examples
test-logging: volumes
	@echo "Testing dual logging functionality..."
	@echo "1. Creating test certificate..."
	podman run --rm \
		-v certs:/data/certificates \
		-v logs:/data/logs \
		-e CERT_TYPE=self-signed \
		-e DOMAIN=test.local \
		podplay-certbot-debian:latest
	@echo ""
	@echo "2. Testing Apache with dual logging..."
	podman run --rm -d \
		--name apache-test \
		-v certs:/data/certificates:ro \
		-v logs:/data/logs \
		-p 8080:80 -p 8443:443 \
		-e DOMAIN=test.local \
		podplay-apache-debian:latest || true
	@sleep 5
	@echo "Making test requests..."
	curl -s http://localhost:8080/ > /dev/null || true
	curl -s -k https://localhost:8443/ > /dev/null || true
	@echo ""
	@echo "3. Checking logs..."
	@echo "Container logs (last 5 lines):"
	@podman logs apache-test --tail 5 || true
	@echo ""
	@echo "Persistent log files:"
	@podman run --rm -v logs:/data/logs alpine:latest ls -la /data/logs/apache/ || true
	@echo ""
	@echo "Access log sample:"
	@podman run --rm -v logs:/data/logs alpine:latest tail -3 /data/logs/apache/access.log || true
	@echo ""
	@echo "Cleaning up..."
	@podman stop apache-test || true
	@podman rm apache-test || true

run-examples: volumes all
	@echo "Running example containers with dual logging..."
	@echo ""
	@echo "Available commands:"
	@echo "  make run-certbot DOMAIN=example.com  - Generate certificates"
	@echo "  make run-apache DOMAIN=example.com   - Run Apache web server"
	@echo "  make run-bind DOMAIN=example.com     - Run DNS server"
	@echo "  make run-mail DOMAIN=example.com     - Run mail server"
	@echo ""
	@echo "Example: make run-certbot DOMAIN=test.local"

run-certbot: volumes
	podman run --rm \
		-v certs:/data/certificates \
		-v logs:/data/logs \
		-e CERT_TYPE=self-signed \
		-e DOMAIN=$(DOMAIN) \
		podplay-certbot-debian:latest

run-apache: volumes
	podman run -d \
		--name apache \
		-v certs:/data/certificates:ro \
		-v logs:/data/logs \
		-p 8080:80 -p 8443:443 \
		-e DOMAIN=$(DOMAIN) \
		podplay-apache-debian:latest

run-bind: volumes
	podman run -d \
		--name bind \
		-v logs:/data/logs \
		-p 53:53/tcp -p 53:53/udp \
		-e DOMAIN_NAME=$(DOMAIN) \
		-e DOMAIN_IP=127.0.0.1 \
		podplay-bind-debian:latest

run-mail: volumes
	podman run -d \
		--name mail \
		-v certs:/data/certificates:ro \
		-v logs:/data/logs \
		-p 25:25 -p 587:587 -p 993:993 \
		-e MAIL_DOMAIN=$(DOMAIN) \
		-e MAIL_SERVER_NAME=mail.$(DOMAIN) \
		podplay-mail-debian:latest

help:
	@echo "Debian Implementation Targets:"
	@echo ""
	@echo "Build Targets:"
	@echo "  all      - Build all Debian service images"
	@echo "  base     - Build base Debian image"
	@echo "  apache   - Build Debian Apache container"
	@echo "  bind     - Build Debian BIND DNS container"
	@echo "  mail     - Build Debian mail server container"
	@echo "  certbot  - Build Debian Certbot container"
	@echo ""
	@echo "Volume Management:"
	@echo "  volumes      - Create required volumes (certs, logs)"
	@echo "  clean-volumes - Remove all volumes (with confirmation)"
	@echo ""
	@echo "Testing:"
	@echo "  test-logging - Test dual logging functionality"
	@echo "  run-examples - Show example run commands"
	@echo ""
	@echo "Running Services:"
	@echo "  run-certbot DOMAIN=<domain> - Generate certificates"
	@echo "  run-apache DOMAIN=<domain>  - Run Apache web server"  
	@echo "  run-bind DOMAIN=<domain>    - Run DNS server"
	@echo "  run-mail DOMAIN=<domain>    - Run mail server"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean        - Remove all Debian images"
	@echo "  help         - Show this help message"