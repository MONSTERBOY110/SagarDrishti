# SagarDrishti data plane (TRD M2). Build from the REPOSITORY ROOT:
#   docker build -f services/api/Dockerfile .
#
# THE LAYOUT INSIDE THE IMAGE IS THE REPOSITORY'S OWN. `app/config.py` finds the
# repo root as three directories above itself and reads `data/`, `storyboards/`
# and `services/api/plugins/` relative to it. Reproducing that layout under
# /srv/sagardrishti means the service runs here exactly as it runs on a
# laptop, with no container-only configuration to drift out of step.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OFFLINE=1

WORKDIR /srv/sagardrishti/services/api

# NO NETWORK CLIENT IN THIS IMAGE. requirements.txt carries `copernicusmarine`
# for tools/fetch_sample.py, which is the one file in the repository that
# fetches data and never runs inside the service. Leaving it out here means the
# deployed data plane physically has no library that could download anything,
# which is a stronger statement than "OFFLINE=1 is the default".
COPY services/api/requirements.txt /tmp/requirements.txt
RUN grep -v -i "^copernicusmarine" /tmp/requirements.txt > /tmp/requirements.image.txt \
 && pip install --no-cache-dir -r /tmp/requirements.image.txt \
 && rm /tmp/requirements*.txt

COPY services/api/app ./app
COPY services/api/plugins ./plugins
COPY storyboards /srv/sagardrishti/storyboards

# data/ is MOUNTED, not copied: it is gitignored, it is the part a deployment
# replaces with its own analysis, and baking it in would make every data
# refresh an image rebuild. See docker-compose.yml.

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
