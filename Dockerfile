# FlasH web API. The desktop app doesn't use Docker.
#   docker build -t flash-api .
#   docker run -p 8000:8000 -v flash-data:/data flash-api
# Then open http://localhost:8000/docs
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASH_DATA_DIR=/data

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY flash/ flash/

# Run as a normal user, not root; decks and progress live in /data.
RUN useradd --create-home flash && mkdir -p /data && chown flash /data
USER flash
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "flash.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
