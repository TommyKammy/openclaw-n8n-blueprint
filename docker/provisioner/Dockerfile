FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash app
USER app
WORKDIR /app

COPY --chown=app:app slack_n8n_provisioner.py /app/slack_n8n_provisioner.py

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "/app/slack_n8n_provisioner.py"]
