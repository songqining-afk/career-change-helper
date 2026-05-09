# ── Stage 1: Build frontend ──
FROM node:22-alpine AS frontend
WORKDIR /app/web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# ── Stage 2: Python backend ──
FROM python:3.12-slim AS backend
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
COPY --from=frontend /app/web/dist ./web/dist

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
