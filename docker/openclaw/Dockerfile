FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 tini \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@latest gog

RUN useradd -m -u 1000 -s /bin/bash openclaw
USER openclaw
WORKDIR /home/openclaw

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["openclaw", "gateway", "--port", "18789"]
