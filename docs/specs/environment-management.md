# Environment and DNS Management Specification

## Purpose
Define a system for managing multiple PodPlay deployments across different environments (VPS, home labs, cloud instances) with centralized DNS coordination and dynamic configuration management.

## Scope
- Multi-environment configuration management
- Centralized DNS zone management
- Dynamic DNS record generation
- Environment inventory tracking
- Hot-reload configuration updates
- Web-based management interface

## Requirements

### Functional Requirements
1. Support multiple deployment environments with different configurations
2. Centralize DNS management on authoritative servers
3. Enable dynamic DNS record updates across environments
4. Track environment inventory (hosts, IPs, services, capabilities)
5. Provide web interface for environment and DNS management
6. Support hot-reload of configuration changes

### Non-Functional Requirements
1. Follow existing user-data volume pattern for consistency
2. Maintain backward compatibility with existing .env files
3. Support both manual and automated DNS updates
4. Provide audit trail for configuration changes
5. Ensure secure communication between environments

## Design

### Environment Configuration Structure

#### Volume Structure
```
/data/environments/
├── config/
│   ├── environments.yaml      # Environment inventory
│   ├── dns-zones.yaml        # DNS zone configurations
│   └── service-endpoints.yaml # Shared service registry
├── templates/
│   ├── env.template          # .env file template
│   └── zone.template         # BIND zone template
└── generated/
    ├── zones/                # Generated BIND zones
    └── configs/              # Generated configs
```

#### Environment Inventory Format
```yaml
# /data/environments/config/environments.yaml
version: "1.0"
environments:
  - name: lab
    description: "Home lab environment"
    location: "Home Network"
    deployment:
      domain: lab.sethlakowske.com
      ip: 192.168.1.100
      public_ip: dynamic
      port_forwarding:
        http: 8080
        https: 8443
    services:
      - apache
      - mail
    capabilities:
      - port_forwarding_required
      - dynamic_dns
    
  - name: sethcore
    description: "Primary VPS"
    location: "Digital Ocean"
    deployment:
      domain: sethcore.com
      ip: 204.44.100.3
      public_ip: 204.44.100.3
    services:
      - apache
      - bind
      - mail
    capabilities:
      - authoritative_dns
      - static_ip
      - ptr_record
    
  - name: vps-mail
    description: "Secondary mail server"
    location: "OVH Canada"
    deployment:
      domain: mail2.sethlakowske.com
      ip: 15.204.246.37
      public_ip: 15.204.246.37
    services:
      - mail
    capabilities:
      - ptr_record
      - static_ip

metadata:
  updated: "2025-01-24T10:00:00Z"
  updated_by: "admin"
```

#### DNS Zone Configuration
```yaml
# /data/environments/config/dns-zones.yaml
version: "1.0"
zones:
  - domain: sethlakowske.com
    ttl: 3600
    soa:
      primary: ns1.sethcore.com
      email: admin.sethlakowske.com
      serial: auto  # YYYYMMDDNN format
      refresh: 7200
      retry: 3600
      expire: 1209600
      minimum: 3600
    
    records:
      # A Records - reference environment IPs
      - type: A
        name: "@"
        value: "{{env:sethcore.public_ip}}"
      
      - type: A
        name: lab
        value: "{{env:lab.public_ip}}"
        
      - type: A
        name: mail2
        value: "{{env:vps-mail.public_ip}}"
      
      # MX Records
      - type: MX
        priority: 10
        value: mail.sethcore.com
        
      - type: MX
        priority: 20
        value: mail2.sethlakowske.com
      
      # CNAME Records
      - type: CNAME
        name: www
        value: sethcore.com
      
      # TXT Records
      - type: TXT
        name: "@"
        value: "v=spf1 mx ip4:{{env:sethcore.public_ip}} ip4:{{env:vps-mail.public_ip}} -all"
      
      - type: TXT
        name: "_dmarc"
        value: "v=DMARC1; p=quarantine; rua=mailto:dmarc@sethlakowske.com"

  - domain: sethcore.com
    ttl: 3600
    records:
      - type: A
        name: "@"
        value: "{{env:sethcore.public_ip}}"
      
      - type: A
        name: www
        value: "{{env:sethcore.public_ip}}"
      
      - type: MX
        priority: 10
        value: mail.sethcore.com
```

### Environment Manager Component

#### Core Functionality
```python
# /data/src/environment_manager.py
class EnvironmentManager:
    """Manages environment configurations and DNS zones"""
    
    def __init__(self):
        self.env_config_path = "/data/environments/config/environments.yaml"
        self.dns_config_path = "/data/environments/config/dns-zones.yaml"
        self.generated_path = "/data/environments/generated"
    
    def add_environment(self, env_config):
        """Add new environment to inventory"""
        
    def update_environment(self, name, updates):
        """Update environment configuration"""
        
    def generate_dns_zones(self):
        """Generate BIND zone files from configuration"""
        
    def deploy_environment(self, name):
        """Generate deployment configuration for environment"""
        
    def sync_dns_to_authoritative(self, zone):
        """Push DNS updates to authoritative server"""
```

#### Hot Reload Capability
```python
class EnvironmentConfigWatcher:
    """Watch for environment configuration changes"""
    
    def on_environment_change(self, event):
        """Handle environment.yaml changes"""
        # Regenerate affected configurations
        # Notify dependent services
        
    def on_dns_change(self, event):
        """Handle dns-zones.yaml changes"""
        # Regenerate zone files
        # Reload BIND if local
        # Push to authoritative if remote
```

### Web Management Interface

#### CGI Endpoints
```
/cgi-bin/admin/environments/
├── list.py          # List all environments
├── add.py           # Add new environment
├── update.py        # Update environment
├── deploy.py        # Deploy to environment
└── status.py        # Check environment status

/cgi-bin/admin/dns/
├── zones.py         # Manage DNS zones
├── records.py       # Add/edit DNS records
├── sync.py          # Sync to authoritative
└── validate.py      # Validate DNS config
```

#### Web UI Pages
```
/admin/environments/
├── index.html       # Environment dashboard
├── add.html         # Add environment form
└── edit.html        # Edit environment

/admin/dns/
├── index.html       # DNS management
├── zones.html       # Zone editor
└── records.html     # Record management
```

### Integration with Existing Systems

#### Extended .env Variables
```bash
# Additional variables for environment management
PODPLAY_ENV_NAME=vps-mail
PODPLAY_ENV_ROLE=mail-secondary
PODPLAY_DNS_AUTHORITATIVE=sethcore.com
PODPLAY_DNS_UPDATE_KEY=/data/environments/keys/dns-update.key
```

#### Makefile Integration
```makefile
# Environment management targets
env-list:
    @podman run --rm \
        -v environments:/data/environments:ro \
        podplay-base:latest \
        /data/src/environment_manager.py --list

env-add:
    @podman run --rm -it \
        -v environments:/data/environments \
        podplay-base:latest \
        /data/src/environment_manager.py --add

env-deploy:
    @podman run --rm \
        -v environments:/data/environments:ro \
        -v /var/run/podman/podman.sock:/var/run/podman/podman.sock \
        podplay-base:latest \
        /data/src/environment_manager.py --deploy $(ENV)

dns-sync:
    @podman run --rm \
        -v environments:/data/environments:ro \
        podplay-base:latest \
        /data/src/environment_manager.py --sync-dns
```

## Implementation Guidelines

### Bootstrap Process
1. Create environments volume on authoritative DNS server
2. Initialize with existing environment configurations
3. Generate initial DNS zones from current setup
4. Deploy environment manager to authoritative server
5. Gradually migrate other environments to use central config

### Security Considerations
1. Use TSIG keys for secure DNS updates
2. Implement RBAC for web interface
3. Encrypt sensitive configuration data
4. Audit all configuration changes
5. Validate all DNS records before deployment

### Migration Path
1. Start with read-only environment inventory
2. Add DNS zone generation capability
3. Implement hot-reload for local changes
4. Add remote DNS update capability
5. Deploy web management interface

## Testing Strategy

### Unit Tests
- Environment YAML parsing and validation
- DNS zone generation with variable substitution
- Record validation (A, MX, CNAME, TXT)
- Configuration hot-reload triggers

### Integration Tests
- Full environment deployment
- DNS zone deployment to BIND
- Multi-environment DNS updates
- Web interface CRUD operations

### Acceptance Criteria
1. Can manage 10+ environments from single interface
2. DNS changes propagate within 5 minutes
3. No service disruption during updates
4. Complete audit trail of all changes
5. Rollback capability for configurations

## Future Enhancements

1. **Automated Deployment**
   - CI/CD integration
   - Automated environment provisioning
   - Health monitoring across environments

2. **Advanced DNS Features**
   - GeoDNS support
   - Failover DNS records
   - Dynamic DNS for home labs

3. **Service Discovery**
   - Automatic service registration
   - Health-based DNS responses
   - Load balancing via DNS

4. **Backup and Sync**
   - Configuration backup to git
   - Multi-master DNS sync
   - Disaster recovery automation