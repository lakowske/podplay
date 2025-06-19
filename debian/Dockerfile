FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create certificate group and user for shared certificate access
RUN groupadd -g 9999 certgroup && \
    useradd -u 9999 -g certgroup -M -s /usr/sbin/nologin certuser

CMD ["/bin/bash"]