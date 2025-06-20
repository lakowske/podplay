# Mail Service Specification

## Purpose
Define the requirements and implementation for a complete mail server solution using Postfix and Dovecot.

## Scope
- SMTP server (Postfix) for sending/receiving mail
- IMAP/POP3 server (Dovecot) for mail retrieval
- Virtual mailbox architecture
- TLS encryption for all protocols
- Authentication and authorization

## Requirements

### Functional Requirements
1. Send and receive email via SMTP (ports 25, 587, 465)
2. Provide IMAP access (ports 143, 993)
3. Provide POP3 access (ports 110, 995)
4. Support virtual domains and mailboxes
5. Implement STARTTLS and implicit TLS
6. Authentication for mail submission

### Non-Functional Requirements
1. Secure by default configuration
2. Modern TLS protocols only
3. Spam and abuse prevention
4. Efficient mail storage
5. < 150MB container image

## Critical Design Decisions

### Hostname Configuration
**CRITICAL**: The mail server hostname (`myhostname`) MUST be different from any virtual domain to prevent mail routing conflicts.

```bash
# Correct configuration
myhostname = mail.example.com
virtual_mailbox_domains = example.com

# INCORRECT - causes routing loops
myhostname = example.com
virtual_mailbox_domains = example.com
```

### Virtual Mailbox Architecture
```
/var/mail/vhosts/
├── example.com/
│   ├── user1/
│   │   ├── cur/
│   │   ├── new/
│   │   └── tmp/
│   └── user2/
└── another.com/
    └── admin/
```

## Implementation

### Dockerfile Structure
```dockerfile
FROM base-debian:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    postfix \
    postfix-pcre \
    dovecot-core \
    dovecot-imapd \
    dovecot-pop3d \
    dovecot-lmtpd \
    opendkim \
    opendkim-tools \
    && rm -rf /var/lib/apt/lists/*

# Create mail user and directories
RUN groupadd -g 5000 vmail && \
    useradd -g vmail -u 5000 vmail -d /var/mail -s /usr/sbin/nologin && \
    mkdir -p /var/mail/vhosts && \
    chown -R vmail:vmail /var/mail

# Add mail users to certgroup
RUN usermod -a -G certgroup postfix && \
    usermod -a -G certgroup dovecot

COPY configs/ /etc/
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

EXPOSE 25 587 465 143 993 110 995

ENTRYPOINT ["/entrypoint.sh"]
```

### Postfix Configuration Template
```bash
# main.cf.template
# Identity
myhostname = ${MAIL_HOSTNAME}
mydomain = ${MAIL_DOMAIN}
myorigin = $mydomain

# Network
mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128 ${TRUSTED_NETWORKS}
inet_interfaces = all
inet_protocols = all

# Virtual domains
virtual_mailbox_domains = ${MAIL_DOMAIN}
virtual_mailbox_base = /var/mail/vhosts
virtual_mailbox_maps = hash:/etc/postfix/vmailbox
virtual_alias_maps = hash:/etc/postfix/virtual
virtual_uid_maps = static:5000
virtual_gid_maps = static:5000

# TLS Configuration
smtpd_tls_cert_file = ${CERT_PATH}/fullchain.pem
smtpd_tls_key_file = ${CERT_PATH}/privkey.pem
smtpd_use_tls = yes
smtpd_tls_auth_only = yes
smtpd_tls_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1
smtpd_tls_ciphers = high
smtpd_tls_mandatory_ciphers = high

# Authentication
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes
smtpd_sasl_security_options = noanonymous
smtpd_sasl_local_domain = $myhostname

# Restrictions
smtpd_recipient_restrictions =
    permit_mynetworks,
    permit_sasl_authenticated,
    reject_unauth_destination,
    reject_rbl_client zen.spamhaus.org

# Message size limit (25MB)
message_size_limit = 26214400

# Mailbox size limit (1GB)
mailbox_size_limit = 1073741824
```

### Dovecot Configuration
```bash
# dovecot.conf
protocols = imap pop3 lmtp

# Authentication
auth_mechanisms = plain login
disable_plaintext_auth = yes

# Mail location
mail_location = maildir:/var/mail/vhosts/%d/%n
mail_uid = vmail
mail_gid = vmail

# SSL/TLS
ssl = required
ssl_cert = <${CERT_PATH}/fullchain.pem
ssl_key = <${CERT_PATH}/privkey.pem
ssl_protocols = !SSLv3 !TLSv1 !TLSv1.1
ssl_cipher_list = ECDHE+AESGCM:ECDHE+AES256:ECDHE+AES128

# Authentication service for Postfix
service auth {
    unix_listener /var/spool/postfix/private/auth {
        mode = 0660
        user = postfix
        group = postfix
    }
}

# LMTP service for mail delivery
service lmtp {
    unix_listener /var/spool/postfix/private/dovecot-lmtp {
        mode = 0600
        user = postfix
        group = postfix
    }
}
```

### Master.cf Configuration
```bash
# Submission port (587) with STARTTLS
submission inet n - n - - smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_recipient_restrictions=permit_sasl_authenticated,reject

# SMTPS port (465) with implicit TLS
smtps inet n - n - - smtpd
  -o syslog_name=postfix/smtps
  -o smtpd_tls_wrappermode=yes
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_recipient_restrictions=permit_sasl_authenticated,reject
```

### Virtual Mailbox Management

#### User Database Format
```bash
# /etc/postfix/vmailbox
user1@example.com    example.com/user1/
user2@example.com    example.com/user2/
admin@another.com    another.com/admin/
```

#### Password Database
```bash
# /etc/dovecot/users
user1@example.com:{PLAIN}password1
user2@example.com:{SHA512-CRYPT}$6$salt$hash...
admin@another.com:{PLAIN}admin123
```

### Entrypoint Script
```bash
#!/bin/bash
set -e

# Validate critical configuration
if [ "${MAIL_HOSTNAME}" == "${MAIL_DOMAIN}" ]; then
    echo "ERROR: MAIL_HOSTNAME cannot be the same as MAIL_DOMAIN"
    echo "Set MAIL_HOSTNAME to something like mail.${MAIL_DOMAIN}"
    exit 1
fi

# Wait for certificates
wait_for_certificates() {
    while [ ! -f "${CERT_PATH}/fullchain.pem" ]; do
        echo "Waiting for certificates..."
        sleep 5
    done
}

# Generate configurations
generate_configs() {
    # Postfix
    envsubst < /etc/postfix/main.cf.template > /etc/postfix/main.cf
    
    # Generate virtual mailbox maps
    postmap /etc/postfix/vmailbox
    postmap /etc/postfix/virtual
    
    # Dovecot
    envsubst < /etc/dovecot/dovecot.conf.template > /etc/dovecot/dovecot.conf
}

# Fix permissions
fix_permissions() {
    chown -R vmail:vmail /var/mail
    chmod -R 700 /var/mail/vhosts
    
    # Certificate access
    chmod 640 ${CERT_PATH}/privkey.pem
    chgrp certgroup ${CERT_PATH}/privkey.pem
}

# Start services
start_services() {
    # Start Dovecot
    dovecot
    
    # Start Postfix in foreground
    postfix start-fg
}

# Main
wait_for_certificates
generate_configs
fix_permissions
start_services
```

## Security Configuration

### SPF Record
```dns
example.com.  IN TXT  "v=spf1 mx -all"
```

### DKIM Setup
```bash
# Generate DKIM key
opendkim-genkey -s mail -d example.com

# DNS record
mail._domainkey.example.com. IN TXT "v=DKIM1; k=rsa; p=MIGfMA0..."
```

### DMARC Policy
```dns
_dmarc.example.com.  IN TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"
```

### Rate Limiting
```bash
# Postfix rate limits
smtpd_client_connection_rate_limit = 10
smtpd_client_message_rate_limit = 20
```

## Testing Procedures

### SMTP Testing
```bash
# Test SMTP connection
telnet localhost 25
HELO test
MAIL FROM: <test@example.com>
RCPT TO: <user@example.com>
DATA
Subject: Test
Test message
.
QUIT

# Test SMTP AUTH
echo -ne "\0user@example.com\0password" | base64
```

### IMAP Testing
```bash
# Test IMAP connection
openssl s_client -connect localhost:993
A001 LOGIN user@example.com password
A002 LIST "" "*"
A003 SELECT INBOX
A004 LOGOUT
```

### TLS Testing
```bash
# Test STARTTLS
openssl s_client -starttls smtp -connect localhost:587
openssl s_client -starttls imap -connect localhost:143
```

## Monitoring

### Mail Queue
```bash
# Check mail queue
postqueue -p

# Flush queue
postqueue -f
```

### Log Monitoring
```bash
# Mail logs
tail -f /var/log/mail.log
tail -f /var/log/mail.err
```

### Health Checks
```bash
# Service status
postfix status
doveadm process status
```

## Volume Management

### Persistent Volumes
```bash
# Mail storage
podman volume create mail-data

# Logs
podman volume create mail-logs

# Running with volumes
podman run -d \
    --name mail \
    -p 25:25 -p 587:587 -p 465:465 \
    -p 143:143 -p 993:993 \
    -p 110:110 -p 995:995 \
    -v certs:/data/certificates:ro \
    -v mail-data:/var/mail \
    -v mail-logs:/var/log \
    -e MAIL_HOSTNAME=mail.example.com \
    -e MAIL_DOMAIN=example.com \
    podplay-mail-debian:latest
```

## Future Enhancements

1. **Advanced Features**
   - Sieve filtering support
   - Virus scanning (ClamAV)
   - Spam filtering (SpamAssassin)
   - Webmail interface

2. **Scalability**
   - Database backend for users
   - Distributed storage
   - Load balancing

3. **Management**
   - Web-based administration
   - Automated user provisioning
   - Quota management
   - Backup and restore