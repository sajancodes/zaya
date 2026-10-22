# Multi-stage Dockerfile: Builds React frontend and serves with FastAPI
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY web/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY web/ ./web/
# Copy compiled React frontend into dist/
COPY --from=frontend-builder /app/dist/ ./web/dist/

EXPOSE 8000
CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
