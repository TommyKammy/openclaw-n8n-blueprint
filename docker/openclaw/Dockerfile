FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 tini git \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@latest gog

RUN useradd -m -u 1001 -s /bin/bash openclaw
USER openclaw
WORKDIR /home/openclaw

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["openclaw", "gateway", "--port", "18789"]
