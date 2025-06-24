#!/bin/bash
# Health monitor for mail services managed by supervisord

log_message() {
    echo "[$(date -Iseconds)] [INFO] [MAIL] [HEALTH-MONITOR]: $1"
}

check_ports() {
    local ports_ok=true
    
    # Check SMTP port 25
    if netstat -ln | grep -q ":25 "; then
        log_message "✓ SMTP port 25 is listening"
    else
        log_message "✗ SMTP port 25 is not listening"
        ports_ok=false
    fi
    
    # Check submission port 587
    if netstat -ln | grep -q ":587 "; then
        log_message "✓ Submission port 587 is listening"
    else
        log_message "⚠ Submission port 587 is not listening"
    fi
    
    # Check IMAPS port 993
    if netstat -ln | grep -q ":993 "; then
        log_message "✓ IMAPS port 993 is listening"
    else
        log_message "⚠ IMAPS port 993 is not listening"
    fi
    
    return $($ports_ok && echo 0 || echo 1)
}

main() {
    log_message "Mail health monitor started"
    
    while true; do
        sleep 60  # Check every minute
        
        # Check port status
        check_ports
        
        # Check supervisord managed processes
        if supervisorctl status > /dev/null 2>&1; then
            log_message "✓ Supervisord is responsive"
            
            # Log any stopped processes
            stopped_services=$(supervisorctl status | grep -v RUNNING | grep -v "health-monitor")
            if [ -n "$stopped_services" ]; then
                log_message "⚠ Some services are not running:"
                echo "$stopped_services" | while IFS= read -r line; do
                    log_message "  $line"
                done
            fi
        else
            log_message "✗ Supervisord is not responsive"
        fi
        
        # Periodic detailed check every 5 minutes
        if [ $(($(date +%s) % 300)) -eq 0 ]; then
            log_message "Performing detailed health check..."
            supervisorctl status | while IFS= read -r line; do
                log_message "Service status: $line"
            done
        fi
    done
}

main "$@"