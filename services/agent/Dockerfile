# Samudra Sahayak, the agent plane (TRD M4). Build from the REPOSITORY ROOT:
#   docker build -f services/agent/Dockerfile .
#
# A separate image on purpose. The agent reaches the data plane over its public
# HTTP API and nothing else, so it can be scaled, replaced or switched off
# without touching the service that holds the data; every P0 requirement still
# passes with this container stopped.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SAGAR_API_BASE=http://api:8000

WORKDIR /srv/sagardrishti/services/agent

COPY services/agent/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY services/agent/app ./app

EXPOSE 8010

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/healthz', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
