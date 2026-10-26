FROM node:24.11.1-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12.14-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/sem/backend SEM_DATA_DIR=/data SEM_STATIC_DIR=/opt/sem/frontend/dist
WORKDIR /opt/sem
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && groupadd --gid 10001 sem && useradd --uid 10001 --gid 10001 --no-create-home sem && mkdir /data && chown 10001:10001 /data
COPY backend/app/ ./backend/app/
COPY --from=frontend /build/dist/ ./frontend/dist/
COPY docs/third-party/ ./licenses/
USER 10001:10001
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health/live',timeout=3)"]
CMD ["uvicorn","app.main:create_app","--factory","--host","0.0.0.0","--port","8080","--workers","1","--no-access-log"]
