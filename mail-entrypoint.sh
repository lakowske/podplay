#!/bin/bash

# Certificate base directory
CERT_BASE="/data/certificates"

# Get domain from environment or certificate info
if [ -n "$DOMAIN" ]; then
    FQDN="$DOMAIN"
elif [ -f "$CERT_BASE/domain.txt" ]; then
    FQDN=$(cat "$CERT_BASE/domain.txt")
else
    FQDN="localhost"
fi

echo "Setting up mail services for domain: $FQDN"

# Certificate directory
CERT_DIR="$CERT_BASE/$FQDN"

# Wait for certificates to be available
echo "Checking for certificates in $CERT_DIR..."
while [ ! -f "$CERT_DIR/fullchain.pem" ] || [ ! -f "$CERT_DIR/privkey.pem" ]; do
    echo "Waiting for certificates to be generated..."
    sleep 5
done
echo "Certificates found!"

# Create mail directories
mkdir -p /var/mail /var/spool/postfix /etc/postfix /etc/dovecot/conf.d

# Configure Postfix (SMTP with SSL/TLS)
echo "Configuring Postfix for SMTP with SSL/TLS..."

cat > /etc/postfix/main.cf << EOF
# Basic configuration
myhostname = $FQDN
mydomain = $FQDN
myorigin = $FQDN
inet_interfaces = all
mydestination = $FQDN, localhost.localdomain, localhost
home_mailbox = Maildir/
mailbox_command = 

# SSL/TLS Configuration
smtpd_tls_cert_file = $CERT_DIR/fullchain.pem
smtpd_tls_key_file = $CERT_DIR/privkey.pem
smtpd_tls_security_level = may
smtpd_tls_session_cache_database = btree:/var/lib/postfix/smtpd_scache
smtp_tls_session_cache_database = btree:/var/lib/postfix/smtp_scache

# SMTP AUTH
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes
smtpd_sasl_security_options = noanonymous
broken_sasl_auth_clients = yes

# Security
smtpd_recipient_restrictions = permit_sasl_authenticated, permit_mynetworks, reject_unauth_destination
smtpd_client_restrictions = permit_sasl_authenticated, permit_mynetworks
smtpd_sender_restrictions = permit_sasl_authenticated, permit_mynetworks

# Enable submission port (587) with mandatory TLS
EOF

cat > /etc/postfix/master.cf << EOF
# Postfix master process configuration file
smtp      inet  n       -       n       -       -       smtpd
submission inet n       -       n       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_reject_unlisted_recipient=no
  -o smtpd_client_restrictions=permit_sasl_authenticated,reject
  -o milter_macro_daemon_name=ORIGINATING
pickup    unix  n       -       n       60      1       pickup
cleanup   unix  n       -       n       -       0       cleanup
qmgr      unix  n       -       n       300     1       qmgr
tlsmgr    unix  -       -       n       1000?   1       tlsmgr
rewrite   unix  -       -       n       -       -       trivial-rewrite
bounce    unix  -       -       n       -       0       bounce
defer     unix  -       -       n       -       0       bounce
trace     unix  -       -       n       -       0       bounce
verify    unix  -       -       n       -       1       verify
flush     unix  n       -       n       1000?   0       flush
proxymap  unix  -       -       n       -       -       proxymap
proxywrite unix -       -       n       -       1       proxymap
smtp      unix  -       -       n       -       -       smtp
relay     unix  -       -       n       -       -       smtp
showq     unix  n       -       n       -       -       showq
error     unix  -       -       n       -       -       error
retry     unix  -       -       n       -       -       error
discard   unix  -       -       n       -       -       discard
local     unix  -       n       n       -       -       local
virtual   unix  -       n       n       -       -       virtual
lmtp      unix  -       -       n       -       -       lmtp
anvil     unix  -       -       n       -       1       anvil
scache    unix  -       -       n       -       1       scache
EOF

# Configure Dovecot (IMAP with SSL/TLS)
echo "Configuring Dovecot for IMAP with SSL/TLS..."

# Use a simpler approach - use defaults and override in conf.d
mkdir -p /etc/dovecot/conf.d

# Main config with just protocols
cat > /etc/dovecot/dovecot.conf << EOF
dovecot_config_version = 2.4.1
protocols = imap lmtp
!include conf.d/*.conf
EOF

# Auth config
cat > /etc/dovecot/conf.d/10-auth.conf << EOF
auth_mechanisms = plain login

passdb {
  driver = passwd-file
  args = /etc/dovecot/users
}

userdb {
  driver = static
  args = uid=vmail gid=vmail home=/var/mail/%u
}
EOF

# Mail config
cat > /etc/dovecot/conf.d/10-mail.conf << EOF
mail_location = maildir:/var/mail/%u
first_valid_uid = 1000
EOF

# SSL config
cat > /etc/dovecot/conf.d/10-ssl.conf << EOF
ssl = required
ssl_cert = <$CERT_DIR/fullchain.pem
ssl_key = <$CERT_DIR/privkey.pem
EOF

# Master config
cat > /etc/dovecot/conf.d/10-master.conf << EOF
service imap-login {
  inet_listener imap {
    port = 143
  }
  inet_listener imaps {
    port = 993
    ssl = yes
  }
}

service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    group = postfix
    mode = 0600
    user = postfix
  }
}

service auth {
  unix_listener /var/spool/postfix/private/auth {
    group = postfix
    mode = 0660
    user = postfix
  }
}
EOF

# Logging
cat > /etc/dovecot/conf.d/10-logging.conf << EOF
log_path = /var/log/dovecot.log
info_log_path = /var/log/dovecot-info.log
EOF

# Create vmail user (check if it doesn't exist)
if ! id vmail >/dev/null 2>&1; then
    adduser -D -s /bin/false -u 5000 vmail
fi
mkdir -p /var/mail
chown -R vmail:vmail /var/mail 2>/dev/null || true

# Create admin user
echo "Creating admin user: admin@$FQDN"
ADMIN_USER="admin@$FQDN"
mkdir -p "/var/mail/admin@$FQDN"
chown vmail:vmail "/var/mail/admin@$FQDN" 2>/dev/null || true

# Create password hash for "password"
ADMIN_PASS_HASH=$(openssl passwd -1 password)
echo "$ADMIN_USER:$ADMIN_PASS_HASH" > /etc/dovecot/users
chmod 600 /etc/dovecot/users

echo "Admin user created: $ADMIN_USER with password: password"

# Set permissions on certificates for mail services
chgrp postfix "$CERT_DIR/fullchain.pem" "$CERT_DIR/privkey.pem" 2>/dev/null || true
chgrp dovecot "$CERT_DIR/fullchain.pem" "$CERT_DIR/privkey.pem" 2>/dev/null || true

# Start services
echo "Starting mail services..."

# Start Postfix
postfix start

# Start Dovecot  
dovecot

# Keep container running
echo "Mail services started successfully!"
echo "SMTP: port 25 (STARTTLS), port 587 (TLS required)"
echo "IMAP: port 143 (STARTTLS), port 993 (TLS)"
echo "Admin user: $ADMIN_USER"
echo "Password: password"

# Keep container running
if [ $# -eq 0 ]; then
    tail -f /var/log/dovecot.log /var/log/postfix.log 2>/dev/null || tail -f /dev/null
else
    exec "$@"
fi