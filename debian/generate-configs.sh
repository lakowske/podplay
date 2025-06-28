#!/bin/bash
# Generate pod YAML files from templates using environment variables

set -e

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found. Please create one or copy from .env.lab or .env.sethcore"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Generate pod YAML files
echo "Generating pod YAML files for domain: $PODPLAY_DOMAIN"

# Check network mode
NETWORK_MODE="${PODPLAY_NETWORK_MODE:-pod}"
echo "  Network mode: $NETWORK_MODE"

for template in pod-yaml/*.yaml.template; do
    if [ -f "$template" ]; then
        output="${template%.template}"
        echo "  - Generating $(basename $output)"
        
        # Generate the base YAML from template
        envsubst < "$template" > "$output.tmp"
        
        # For podplay-pod.yaml, add hostNetwork if in host mode
        if [[ "$(basename $output)" == "podplay-pod.yaml" ]] && [[ "$NETWORK_MODE" == "host" ]]; then
            # Add hostNetwork: true after hostname line
            sed -i '/^  hostname: podplay$/a\  hostNetwork: true' "$output.tmp"
            
            # Remove hostPort lines when using host networking
            sed -i '/hostPort:/d' "$output.tmp"
        fi
        
        mv "$output.tmp" "$output"
    fi
done

echo "Configuration files generated successfully!"
echo ""
echo "Current configuration:"
echo "  Domain: $PODPLAY_DOMAIN"
echo "  Network Mode: $NETWORK_MODE"
echo "  HTTP Port: $PODPLAY_HOST_HTTP_PORT"
echo "  HTTPS Port: $PODPLAY_HOST_HTTPS_PORT"
echo "  SMTP Port: $PODPLAY_HOST_SMTP_PORT"
echo "  Submission Port: $PODPLAY_HOST_SUBMISSION_PORT"
echo "  IMAPS Port: $PODPLAY_HOST_IMAPS_PORT"
echo "  Certificate Type: $PODPLAY_CERT_TYPE"