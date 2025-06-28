#!/bin/bash
# Real-time mail queue monitor for spam detection
# Monitors postfix queue and alerts on suspicious activity

LOG_FILE="/data/logs/mail/queue-monitor.log"
ALERT_THRESHOLD=5  # Alert if more than 5 messages in queue
CHECK_INTERVAL=30  # Check every 30 seconds

log_message() {
    echo "[$(date -Iseconds)] [QUEUE-MONITOR] $1" | tee -a "$LOG_FILE"
}

check_queue() {
    # Count messages in queue (excluding normal control files)
    QUEUE_COUNT=$(find /var/spool/postfix/active /var/spool/postfix/incoming /var/spool/postfix/deferred /var/spool/postfix/maildrop -name "*" -type f 2>/dev/null | wc -l)
    
    if [ "$QUEUE_COUNT" -gt "$ALERT_THRESHOLD" ]; then
        log_message "ALERT: $QUEUE_COUNT messages in queue (threshold: $ALERT_THRESHOLD)"
        
        # Log sample queue entries for analysis
        log_message "Queue sample:"
        /usr/sbin/postqueue -p 2>/dev/null | head -20 | while read line; do
            log_message "  $line"
        done
        
        # Check for suspicious patterns
        SUSPICIOUS=$(/usr/sbin/postqueue -p 2>/dev/null | grep -E "([@][a-z0-9]{6,15}[@]|[@][a-z]{2,8}[@])" | wc -l)
        if [ "$SUSPICIOUS" -gt 0 ]; then
            log_message "WARNING: $SUSPICIOUS messages with suspicious sender patterns detected"
        fi
        
        return 1  # Alert condition
    else
        log_message "Queue normal: $QUEUE_COUNT messages"
        return 0  # Normal condition
    fi
}

# Initialize monitoring
log_message "Mail queue monitor started (threshold: $ALERT_THRESHOLD messages, interval: ${CHECK_INTERVAL}s)"

# Main monitoring loop
while true; do
    if ! check_queue; then
        # Alert condition - could trigger additional actions here
        log_message "Queue alert triggered - consider investigation"
    fi
    
    sleep "$CHECK_INTERVAL"
done