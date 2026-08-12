# Builds the merged single-port production mode described in README.md --
# FastAPI serves the built frontend itself (backend/app/main.py's
# FRONTEND_DIST handling), so the final image only ever runs one process.

# --- Stage 1: build the frontend once ---
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend + built frontend ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY licensing/ ./licensing/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Leads/alerts/trial-start persist here (DATABASE_PATH default:
# backend/data/app.db) -- mount a volume at this path to survive
# `docker run --rm`/image upgrades instead of losing data with the container.
RUN mkdir -p /app/backend/data
VOLUME ["/app/backend/data"]

WORKDIR /app/backend
EXPOSE 8081

# --proxy-headers/--forwarded-allow-ips only added when TRUST_PROXY_HEADERS
# is set -- needed so rate limiting (app/middleware.py) sees the real client
# IP instead of the proxy's when this runs behind one. Leave unset for a
# bare container with nothing
# trusted in front of it, or any client could spoof X-Forwarded-For and
# defeat rate limiting entirely.
CMD ["sh", "-c", "if [ \"$TRUST_PROXY_HEADERS\" = \"true\" ]; then exec uvicorn app.main:app --host 0.0.0.0 --port 8081 --proxy-headers --forwarded-allow-ips='*'; else exec uvicorn app.main:app --host 0.0.0.0 --port 8081; fi"]
