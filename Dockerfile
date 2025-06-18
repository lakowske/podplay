FROM alpine:latest

RUN apk add --no-cache \
    bash \
    python3 \
    py3-pip \
    curl

# Create certificate group and user for shared certificate access
RUN addgroup -g 9999 certgroup && \
    adduser -u 9999 -G certgroup -D -H -s /sbin/nologin certuser

CMD ["/bin/bash"]