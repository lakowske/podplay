.PHONY: all base apache bind mail certbot clean help volumes clean-volumes test-logging run-examples
.PHONY: pod-init pod-up pod-down pod-status pod-logs pod-renewal pod-cert-cleanup
.PHONY: user-add user-remove user-list user-test user-reload
.PHONY: test-auth test-auth-clean
.PHONY: generate-configs env-switch env-check

# Load environment configuration if exists
-include .env
export

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
	podman volume create user-data || true
	@echo "Volumes created:"
	@echo "  - certs:     /data/certificates (certificate storage)"
	@echo "  - logs:      /data/logs (persistent logging)"
	@echo "  - user-data: /data/user-data (user configurations and data)"

clean-volumes:
	@echo "Warning: This will remove all Podplay volumes and their data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		podman volume rm user-data || true; \
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
	@podman run --rm -v logs:/data/logs debian:12-slim ls -la /data/logs/apache/ || true
	@echo ""
	@echo "Access log sample:"
	@podman run --rm -v logs:/data/logs debian:12-slim tail -3 /data/logs/apache/access.log || true
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
		-v certs:/data/certificates:rw,z \
		-v logs:/data/logs \
		-e CERT_TYPE=self-signed \
		-e DOMAIN=$(DOMAIN) \
		podplay-certbot-debian:latest

run-apache: volumes
	podman run -d \
		--name apache \
		-v certs:/data/certificates:rw,z \
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
		-v certs:/data/certificates:rw,z \
		-v logs:/data/logs \
		-v user-data:/data/user-data \
		-p 25:25 -p 587:587 -p 993:993 \
		-e MAIL_DOMAIN=$(DOMAIN) \
		-e MAIL_SERVER_NAME=mail.$(DOMAIN) \
		podplay-mail-debian:latest

# Environment configuration targets
generate-configs:
	@./generate-configs.sh

env-check:
	@if [ ! -f ".env" ]; then \
		echo "Error: .env file not found."; \
		echo "Available environments:"; \
		echo "  make env-switch ENV=lab     # For lab.sethlakowske.com"; \
		echo "  make env-switch ENV=sethcore # For sethcore.com"; \
		exit 1; \
	fi
	@echo "Current environment configuration:"
	@echo "  Domain: $${PODPLAY_DOMAIN:-not set}"
	@echo "  HTTP Port: $${PODPLAY_HOST_HTTP_PORT:-not set}"
	@echo "  HTTPS Port: $${PODPLAY_HOST_HTTPS_PORT:-not set}"
	@echo "  SMTP Port: $${PODPLAY_HOST_SMTP_PORT:-not set}"
	@echo "  Submission Port: $${PODPLAY_HOST_SUBMISSION_PORT:-not set}"
	@echo "  IMAPS Port: $${PODPLAY_HOST_IMAPS_PORT:-not set}"

env-switch:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV parameter required"; \
		echo "Usage: make env-switch ENV=lab|sethcore"; \
		exit 1; \
	fi
	@if [ ! -f ".env.$(ENV)" ]; then \
		echo "Error: Environment file .env.$(ENV) not found"; \
		exit 1; \
	fi
	@echo "Switching to $(ENV) environment..."
	@cp .env.$(ENV) .env
	@$(MAKE) generate-configs

# Pod deployment targets
pod-init: volumes env-check generate-configs
	@echo "Starting certificate initialization pod..."
	@echo "This will generate SSL certificates for $${PODPLAY_DOMAIN}"
	@echo "Port $${PODPLAY_HOST_HTTP_PORT} must be available for Let's Encrypt validation"
	podman play kube pod-yaml/podplay-init-pod.yaml
	@echo ""
	@echo "Certificate initialization started. Monitor with:"
	@echo "  podman logs -f podplay-init-certbot"
	@echo ""
	@echo "When complete, clean up with:"
	@echo "  make pod-cert-cleanup"

pod-cert-cleanup:
	@echo "Cleaning up certificate initialization pod..."
	@if podman pod exists podplay-init 2>/dev/null; then \
		echo "Removing completed certificate pod..."; \
		podman play kube --down pod-yaml/podplay-init-pod.yaml || true; \
	else \
		echo "Certificate pod already cleaned up automatically"; \
	fi
	@echo "Ready to start services with:"
	@echo "  make pod-up"

pod-up: volumes env-check generate-configs
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

pod-renewal: volumes env-check generate-configs
	@echo "Running certificate renewal pod..."
	@echo "This will attempt to renew existing Let's Encrypt certificates"
	podman play kube pod-yaml/podplay-renewal-pod.yaml

# User management targets
user-add:
	@if [ -z "$(USER)" ] || [ -z "$(PASS)" ] || [ -z "$(DOMAIN)" ]; then \
		echo "Error: USER, PASS, and DOMAIN are required"; \
		echo "Usage: make user-add USER=username PASS=password DOMAIN=example.com [QUOTA=100M] [SERVICES=mail]"; \
		exit 1; \
	fi
	@echo "Adding user $(USER)@$(DOMAIN)..."
	@podman run --rm \
		-v user-data:/data/user-data \
		podplay-mail-debian:latest \
		/data/src/user_manager.py --add-user \
		--user $(USER) --password $(PASS) --domain $(DOMAIN) \
		--quota $(if $(QUOTA),$(QUOTA),100M) \
		--services $(if $(SERVICES),$(SERVICES),mail)

user-remove:
	@if [ -z "$(USER)" ] || [ -z "$(DOMAIN)" ]; then \
		echo "Error: USER and DOMAIN are required"; \
		echo "Usage: make user-remove USER=username DOMAIN=example.com"; \
		exit 1; \
	fi
	@echo "Removing user $(USER)@$(DOMAIN)..."
	@podman run --rm \
		-v user-data:/data/user-data \
		podplay-mail-debian:latest \
		/data/src/user_manager.py --remove-user \
		--user $(USER) --domain $(DOMAIN)

user-list:
	@echo "Listing users$(if $(DOMAIN), for domain $(DOMAIN))..."
	@podman run --rm \
		-v user-data:/data/user-data \
		podplay-mail-debian:latest \
		/data/src/user_manager.py --list-users $(if $(DOMAIN),--domain $(DOMAIN))

user-test:
	@if [ -z "$(USER)" ] || [ -z "$(PASS)" ] || [ -z "$(DOMAIN)" ]; then \
		echo "Error: USER, PASS, and DOMAIN are required"; \
		echo "Usage: make user-test USER=username PASS=password DOMAIN=example.com"; \
		exit 1; \
	fi
	@echo "Testing authentication for $(USER)@$(DOMAIN)..."
	@echo "Note: This requires a running mail service container"
	@podman exec -it $$(podman ps --filter "name=podplay-mail" --format "{{.Names}}" | head -1) \
		/data/src/user_manager.py --test-auth \
		--user $(USER) --password $(PASS) --domain $(DOMAIN) || \
		echo "Error: No running mail container found. Use 'make pod-up' first."

user-reload:
	@echo "Forcing user configuration reload..."
	@echo "Note: This requires a running mail service container"
	@podman exec -it $$(podman ps --filter "name=podplay-mail" --format "{{.Names}}" | head -1) \
		touch /data/user-data/config/users.yaml || \
		echo "Error: No running mail container found. Use 'make pod-up' first."

# Simple authentication testing
test-auth:
	@cd tests/auth && python3 simple_auth_test.py

test-auth-clean:
	@echo "🧹 Cleaning authentication test reports..."
	@rm -f tests/auth/reports/*.txt tests/auth/reports/*.log 2>/dev/null || true

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
	@echo "Environment Configuration:"
	@echo "  env-check             - Show current environment configuration"
	@echo "  env-switch ENV=<name> - Switch to environment (lab or sethcore)"
	@echo "  generate-configs      - Regenerate pod YAML files from templates"
	@echo ""
	@echo "Pod Deployment Workflow:"
	@echo "  1. make env-switch ENV=<name> - Select your environment"
	@echo "  2. make all                   - Build all container images"
	@echo "  3. make volumes               - Create required volumes"
	@echo "  4. make pod-init              - Generate SSL certificates"
	@echo "  5. make pod-cert-cleanup      - Clean up certificate pod"
	@echo "  6. make pod-up                - Start PodPlay services"
	@echo ""
	@echo "Pod Management:"
	@echo "  pod-status    - Show pod and container status"
	@echo "  pod-logs      - Follow pod logs"
	@echo "  pod-down      - Stop PodPlay services pod"
	@echo "  pod-renewal   - Run certificate renewal"
	@echo ""
	@echo "Volume Management:"
	@echo "  volumes      - Create required volumes (certs, logs, user-data)"
	@echo "  clean-volumes - Remove all volumes (with confirmation)"
	@echo ""
	@echo "Testing:"
	@echo "  test-logging - Test dual logging functionality"
	@echo "  test-auth    - Run authentication tests"
	@echo "  test-auth-clean - Clean up test artifacts"
	@echo "  run-examples - Show example run commands"
	@echo ""
	@echo "User Management:"
	@echo "  user-add USER=<user> PASS=<pass> DOMAIN=<domain> [QUOTA=100M] [SERVICES=mail]"
	@echo "                   - Add a new user"
	@echo "  user-remove USER=<user> DOMAIN=<domain>"
	@echo "                   - Remove a user"
	@echo "  user-list [DOMAIN=<domain>]"
	@echo "                   - List all users or users for specific domain"
	@echo "  user-test USER=<user> PASS=<pass> DOMAIN=<domain>"
	@echo "                   - Test user authentication (requires running mail service)"
	@echo "  user-reload      - Force user configuration reload (requires running mail service)"
	@echo ""
	@echo "Individual Services:"
	@echo "  run-certbot DOMAIN=<domain> - Generate certificates"
	@echo "  run-apache DOMAIN=<domain>  - Run Apache web server"  
	@echo "  run-bind DOMAIN=<domain>    - Run DNS server"
	@echo "  run-mail DOMAIN=<domain>    - Run mail server"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean        - Remove all Debian images"
	@echo "  help         - Show this help message"