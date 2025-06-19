.PHONY: help clean
.PHONY: alpine alpine-all alpine-base alpine-apache alpine-bind alpine-mail alpine-certbot alpine-clean alpine-help
.PHONY: debian debian-all debian-base debian-apache debian-bind debian-mail debian-certbot debian-clean debian-help
.PHONY: build build-all build-base build-apache build-bind build-mail build-certbot

# Backward compatibility targets (delegate to Alpine)
build-all: alpine-all
build: alpine-base
build-base: alpine-base
build-apache: alpine-apache
build-bind: alpine-bind
build-mail: alpine-mail
build-certbot: alpine-certbot

# Alpine targets (delegate to alpine/Makefile)
alpine: alpine-base

alpine-all:
	$(MAKE) -C alpine all

alpine-base:
	$(MAKE) -C alpine base

alpine-apache:
	$(MAKE) -C alpine apache

alpine-bind:
	$(MAKE) -C alpine bind

alpine-mail:
	$(MAKE) -C alpine mail

alpine-certbot:
	$(MAKE) -C alpine certbot

alpine-clean:
	$(MAKE) -C alpine clean

alpine-help:
	$(MAKE) -C alpine help

# Debian targets (delegate to debian/Makefile)
debian: debian-base

debian-all:
	$(MAKE) -C debian all

debian-base:
	$(MAKE) -C debian base

debian-apache:
	$(MAKE) -C debian apache

debian-bind:
	$(MAKE) -C debian bind

debian-mail:
	$(MAKE) -C debian mail

debian-certbot:
	$(MAKE) -C debian certbot

debian-clean:
	$(MAKE) -C debian clean

debian-help:
	$(MAKE) -C debian help

# Global targets
clean: alpine-clean debian-clean
	@echo "All images cleaned"

help:
	@echo "PodPlay Container Build System"
	@echo "============================="
	@echo ""
	@echo "This project supports two implementations:"
	@echo "  - Alpine Linux (lightweight, minimal)"
	@echo "  - Debian (full-featured, stable)"
	@echo ""
	@echo "Quick Start:"
	@echo "  make alpine-all    - Build all Alpine containers"
	@echo "  make debian-all    - Build all Debian containers"
	@echo ""
	@echo "Implementation-specific targets:"
	@echo "  alpine-*           - Alpine Linux implementation"
	@echo "  debian-*           - Debian implementation"
	@echo ""
	@echo "Available services: base, apache, bind, mail, certbot"
	@echo ""
	@echo "For detailed help on each implementation:"
	@echo "  make alpine-help   - Show Alpine-specific targets"
	@echo "  make debian-help   - Show Debian-specific targets"
	@echo ""
	@echo "Backward compatibility (defaults to Alpine):"
	@echo "  make build-all     - Same as alpine-all"
	@echo "  make build-*       - Same as alpine-*"
	@echo ""
	@echo "Global targets:"
	@echo "  clean              - Remove all images (Alpine and Debian)"
	@echo "  help               - Show this help message"