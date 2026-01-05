FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    wireguard-tools \
    iproute2 \
    iputils-ping \
    python3 \
    python3-requests \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy node scripts
COPY scripts/ ./scripts/

# Copy WireGuard config (will be mounted from artifacts/)
# COPY ../artifacts/wg0.conf /etc/wireguard/ (done via docker-compose mount)

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh scripts/*.py scripts/*.sh

# Capabilities needed for WireGuard
ENTRYPOINT ["/app/entrypoint.sh"]
