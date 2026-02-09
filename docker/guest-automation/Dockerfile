FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY guest_automation_service.py /app/guest_automation_service.py

EXPOSE 18111

CMD ["python3", "/app/guest_automation_service.py"]
