# FlasH web API. The desktop app doesn't use Docker.
#   docker build -t flash-api .
#   docker run -p 8000:8000 -v flash-data:/data flash-api
# Then open http://localhost:8000/docs
# Usually started together with the web app: see compose.yaml and docs/DEPLOYMENT.md.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASH_DATA_DIR=/data

WORKDIR /app

# Dependencies first, so code changes don't reinstall them. The lock file pins exact versions.
COPY requirements-api-lock.txt ./
RUN pip install --no-cache-dir -r requirements-api-lock.txt

COPY flash/ flash/

# Run as a normal user, not root; decks and progress live in /data.
RUN useradd --create-home flash && mkdir -p /data && chown flash /data
USER flash
VOLUME /data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"]

# One worker on purpose: open tests live in this process's memory.
# --proxy-headers: trust X-Forwarded-* from nginx, the only thing that can reach this port in Compose.
CMD ["uvicorn", "flash.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
