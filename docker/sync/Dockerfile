FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 docker.io tini \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@latest

WORKDIR /app
COPY openclaw_n8n_sync_worker.py /app/openclaw_n8n_sync_worker.py

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "/app/openclaw_n8n_sync_worker.py"]
