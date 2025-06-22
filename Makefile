.PHONY: help clean all base apache bind mail certbot volumes pod-init pod-cert-cleanup pod-up pod-down pod-status pod-logs auth-cli-install auth-cli-bootstrap auth-cli-test auth-cli-test-quick auth-logs-monitor auth-logs-check

# Main build targets
all:
	$(MAKE) -C debian all

base:
	$(MAKE) -C debian base

apache:
	$(MAKE) -C debian apache

bind:
	$(MAKE) -C debian bind

mail:
	$(MAKE) -C debian mail

certbot:
	$(MAKE) -C debian certbot

# Volume management
volumes:
	$(MAKE) -C debian volumes

# Pod management
pod-init:
	$(MAKE) -C debian pod-init

pod-cert-cleanup:
	$(MAKE) -C debian pod-cert-cleanup

pod-up:
	$(MAKE) -C debian pod-up

pod-down:
	$(MAKE) -C debian pod-down

pod-status:
	$(MAKE) -C debian pod-status

pod-logs:
	$(MAKE) -C debian pod-logs

# Authentication CLI operations
auth-cli-install:
	@echo "Installing authentication CLI tool..."
	@cp debian/podplay-auth /usr/local/bin/
	@chmod +x /usr/local/bin/podplay-auth
	@pip3 install -q click requests pyyaml
	@echo "CLI tool installed at /usr/local/bin/podplay-auth"

auth-cli-bootstrap:
	@echo "Bootstrapping admin access..."
	@podplay-auth bootstrap

auth-cli-test:
	@echo "Running authentication tests..."
	@python3 debian/tests/auth/test_workflows.py

auth-cli-test-quick:
	@echo "Running quick registration test..."
	@podplay-auth test registration-flow \
		-u test_$$(date +%s) \
		-e test_$$(date +%s)@lab.sethlakowske.com \
		-p TestPass123!

auth-logs-monitor:
	@echo "Monitoring authentication logs..."
	@podman exec -it podplay-apache tail -f /data/logs/apache/auth.log

auth-logs-check:
	@echo "Checking recent auth logs..."
	@podman exec podplay-apache tail -20 /data/logs/apache/auth.log

# Cleanup
clean:
	$(MAKE) -C debian clean

clean-volumes:
	$(MAKE) -C debian clean-volumes

help:
	@echo "PodPlay Container Build System"
	@echo "============================="
	@echo ""
	@echo "Build targets:"
	@echo "  all                - Build all containers"
	@echo "  base               - Build base container"
	@echo "  apache             - Build Apache container"
	@echo "  bind               - Build DNS container"
	@echo "  mail               - Build mail container"
	@echo "  certbot            - Build certificate container"
	@echo ""
	@echo "Volume management:"
	@echo "  volumes            - Create named volumes"
	@echo "  clean-volumes      - Remove all volumes (WARNING: destroys data)"
	@echo ""
	@echo "Pod operations:"
	@echo "  pod-init           - Generate certificates"
	@echo "  pod-cert-cleanup   - Remove certificate pod"
	@echo "  pod-up             - Start services"
	@echo "  pod-down           - Stop services"
	@echo "  pod-status         - Check pod status"
	@echo "  pod-logs           - View pod logs"
	@echo ""
	@echo "Authentication CLI:"
	@echo "  auth-cli-install   - Install CLI tool locally"
	@echo "  auth-cli-bootstrap - Bootstrap admin access"
	@echo "  auth-cli-test      - Run authentication tests"
	@echo "  auth-cli-test-quick - Run quick registration test"
	@echo "  auth-logs-monitor  - Monitor auth logs in real-time"
	@echo "  auth-logs-check    - Check recent auth logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean              - Remove all images"
	@echo "  help               - Show this help message"