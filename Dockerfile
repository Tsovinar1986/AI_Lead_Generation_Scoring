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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
