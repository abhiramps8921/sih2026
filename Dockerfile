FROM node:22-alpine AS frontend

WORKDIR /app/work
COPY work/package.json work/package-lock.json ./
RUN npm ci
COPY work/index.html work/vite.config.js ./
COPY work/src ./src
COPY work/public ./public
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    ROAM_DB_PATH=/tmp/roam.db

WORKDIR /app/work
COPY work/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY work/backend ./backend
COPY --from=frontend /app/work/dist ./dist

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app/work
USER appuser

EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT}"]
