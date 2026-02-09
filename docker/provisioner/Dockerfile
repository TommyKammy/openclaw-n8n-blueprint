FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 tini \
    && rm -rf /var/lib/apt/lists/*

# Used for onboarding email delivery (Gmail API)
RUN npm install -g gog

# Install the gmail script used by slack_n8n_provisioner.py
RUN gog -i gmail

USER node
WORKDIR /app

COPY --chown=node:node slack_n8n_provisioner.py /app/slack_n8n_provisioner.py

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "/app/slack_n8n_provisioner.py"]
