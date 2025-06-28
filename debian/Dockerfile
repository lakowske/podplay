FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create certificate group and user for shared certificate access
RUN groupadd -g 9999 certgroup && \
    useradd -u 9999 -g certgroup -M -s /usr/sbin/nologin certuser

# Create logging group and user for shared log access
RUN groupadd -g 9998 loggroup && \
    useradd -u 9998 -g loggroup -M -s /usr/sbin/nologin loguser

# Create virtual environment
RUN python3 -m venv /data/.venv
ENV PATH="/data/.venv/bin:$PATH"

# Copy Python source code
COPY src/ /data/src/

# Install Python dependencies if requirements.txt exists
COPY requirements.txt* /tmp/
RUN if [ -f /tmp/requirements.txt ]; then pip install -r /tmp/requirements.txt; fi && \
    rm -f /tmp/requirements.txt

# Install watchdog for file monitoring (used by multiple services)
RUN pip install watchdog

# Create log directory structure
RUN mkdir -p /data/logs/apache /data/logs/bind /data/logs/mail /data/logs/certbot && \
    chown -R loguser:loggroup /data/logs && \
    chmod 755 /data/logs /data/logs/*

# Make Python scripts executable
RUN chmod +x /data/src/cert_manager.py /data/src/dkim_manager.py

CMD ["/bin/bash"]