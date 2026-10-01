# JARVIS — version web hébergée (VPS). Construit depuis la racine du dépôt :
#   docker compose -f deploy/web/docker-compose.yml up -d --build

# ── 1. Interface (React) ────────────────────────────────────────────────────
FROM node:22-alpine AS ui
WORKDIR /ui
COPY client/package.json client/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY client/ ./
RUN npm run build

# ── 2. Serveur (Python) ─────────────────────────────────────────────────────
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JARVIS_MODE=hosted \
    JARVIS_HOST=0.0.0.0 \
    JARVIS_PORT=8765 \
    JARVIS_LOCAL_MODELS=0 \
    JARVIS_TRUST_PROXY=1 \
    JARVIS_DATA_DIR=/data \
    JARVIS_LOG_DIR=/data/logs \
    JARVIS_WEB_DIR=/app/web \
    JARVIS_MODELS_DIR=/app/models
WORKDIR /app
COPY server/requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
COPY server/ ./
COPY --from=ui /ui/dist ./web
RUN useradd --system --uid 10001 --home /data jarvis \
    && mkdir -p /data /app/models && chown jarvis /data
USER jarvis
VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=4)"
CMD ["python", "main.py"]
