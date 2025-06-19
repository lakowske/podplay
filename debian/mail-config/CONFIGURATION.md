# Debian Mail Server Configuration

This document outlines the configuration and key learnings from implementing a secure mail server with TLS/SSL support using Postfix and Dovecot on Debian.

## Overview

The mail server provides:
- **SMTP** with STARTTLS (port 25) and submission (port 587)
- **SMTPS** with implicit TLS (port 465)  
- **IMAP** with STARTTLS (port 143) and SSL (port 993)
- **POP3** with STARTTLS (port 110) and SSL (port 995)
- **Virtual mailboxes** for domain hosting
- **Let's Encrypt SSL certificates** for production encryption

## Key Configuration Files

### Postfix Configuration

#### `postfix-main.cf`
- **Purpose**: Main Postfix configuration template
- **Key Settings**:
  - `myhostname = mail.${MAIL_DOMAIN}` - **Critical**: Must be different from virtual domain
  - `virtual_mailbox_domains = ${MAIL_DOMAIN}` - Defines virtual domain
  - `virtual_transport = virtual` - Uses virtual delivery agent
  - TLS settings for strong encryption (TLS 1.2+, high ciphers)

#### `master.cf`
- **Purpose**: Postfix services configuration
- **Key Services**:
  - `submission` (port 587): Mandatory TLS for authenticated mail submission
  - `smtps` (port 465): Implicit TLS wrapper mode
  - Both configured with Dovecot SASL authentication

### Dovecot Configuration

#### `dovecot.conf`
- **Purpose**: IMAP/POP3 server with authentication
- **Key Settings**:
  - SSL enabled with Let's Encrypt certificates
  - Virtual users via static authentication
  - LMTP service for Postfix integration

## Critical Configuration Insights

### 1. Hostname vs Virtual Domain Separation

**Problem**: When `myhostname` equals the virtual domain, Postfix treats it as local delivery.

```
# WRONG - Causes routing conflict
myhostname = lab.sethlakowske.com
virtual_mailbox_domains = lab.sethlakowske.com
```

**Solution**: Use different hostname for the mail server.

```
# CORRECT - Enables proper virtual domain routing
myhostname = mail.lab.sethlakowske.com  
virtual_mailbox_domains = lab.sethlakowske.com
```

**Why**: Postfix processes domains in order:
1. `mydestination` (local delivery) - includes `$myhostname`
2. `virtual_mailbox_domains` (virtual delivery)

If a domain appears in both, local delivery wins and virtual mailboxes are never checked.

### 2. TLS Configuration

**Certificate Paths**: Certificates must be accessible to both Postfix and Dovecot with proper permissions.

```bash
# Dovecot certificates
/etc/ssl/dovecot/server.pem (644)
/etc/ssl/dovecot/server.key (640, root:dovecot)

# Postfix certificates  
/etc/ssl/certs/dovecot/fullchain.pem (644)
/etc/ssl/certs/dovecot/privkey.pem (640, root:postfix)
```

**Strong Encryption Settings**:
```
# Disable weak protocols and ciphers
smtpd_tls_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1
smtpd_tls_ciphers = high
smtpd_tls_exclude_ciphers = aNULL, MD5, DES, 3DES, DES-CBC3-SHA, RC4-SHA
```

### 3. Virtual Mailbox Setup

**Directory Structure**:
```
/var/spool/mail/vhosts/
└── lab.sethlakowske.com/
    └── admin/
        ├── cur/
        ├── new/
        └── tmp/
```

**User Mapping**:
```
# /etc/postfix/vmailbox
admin@lab.sethlakowske.com    lab.sethlakowske.com/admin/
```

**Permissions**: All mailbox files owned by `vmail:vmail`.

### 4. Authentication Integration

**Postfix → Dovecot SASL**:
```
# Postfix main.cf
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth

# Postfix master.cf (submission/smtps)
-o smtpd_sasl_auth_enable=yes
-o smtpd_tls_security_level=encrypt
```

**Socket**: `/var/spool/postfix/private/auth` (managed by Dovecot)

## Testing and Verification

### End-to-End Test Results

✅ **SMTP STARTTLS** (port 25): Authentication and encryption working  
✅ **SMTP Submission** (port 587): TLS 1.3 with 256-bit AES encryption  
✅ **SMTPS** (port 465): Implicit TLS working  
✅ **IMAP SSL** (port 993): TLS 1.3 encryption confirmed  
✅ **IMAP STARTTLS** (port 143): Upgrade to TLS working  
✅ **End-to-End Flow**: Send via SMTP TLS → Receive via IMAP TLS ✓

### Encryption Details

All connections achieve:
- **Protocol**: TLS 1.3
- **Cipher**: TLS_AES_256_GCM_SHA384  
- **Encryption**: 256-bit AES
- **Certificates**: Let's Encrypt production certificates

## Common Issues and Solutions

### "User unknown in local recipient table"

**Cause**: Hostname conflicts with virtual domain.  
**Solution**: Use `myhostname = mail.domain.com` instead of `myhostname = domain.com`.

### "TLS not available due to local problem"

**Cause**: Certificate permission or path issues.  
**Solution**: Verify certificate paths and ensure proper ownership (`root:postfix`/`root:dovecot`).

### Missing vmailbox.db

**Cause**: `postmap` command failed during container startup.  
**Solution**: Ensure `/etc/postfix/vmailbox` exists before running `postmap /etc/postfix/vmailbox`.

## Security Best Practices

1. **Mandatory TLS**: Submission ports require encryption (`smtpd_tls_security_level=encrypt`)
2. **Strong Ciphers**: Disable weak protocols and ciphers
3. **Certificate Validation**: Use production Let's Encrypt certificates
4. **User Isolation**: Virtual users separate from system users
5. **File Permissions**: Restrict certificate access to required services only

## Environment Variables

- `MAIL_SERVER_NAME`: Hostname for the mail server (e.g., `lab.sethlakowske.com`)
- `MAIL_DOMAIN`: Virtual domain for mailboxes (e.g., `lab.sethlakowske.com`)
- `SSL_CERT_FILE`: Path to SSL certificate
- `SSL_KEY_FILE`: Path to SSL private key

## Container Integration

The mail server integrates with the certificate container via:
- **Shared Volume**: `certs:/data/certificates`
- **Certificate Path**: `/data/certificates/${MAIL_DOMAIN}/`
- **Auto-detection**: Startup script checks for certificates and configures TLS accordingly

This configuration provides a production-ready mail server with strong encryption and proper virtual domain handling.