FROM node:20-slim AS frontend
WORKDIR /app/frontend

ENV NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_ENABLE_GOOGLE_SSO=false

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM node:20-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NEXT_PUBLIC_API_BASE_URL=/api

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnss3 \
    libpango-1.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
    fonts-liberation \
  && rm -rf /var/lib/apt/lists/*

COPY backend /app/backend
COPY --from=frontend /app/frontend/.next /app/frontend/.next
COPY --from=frontend /app/frontend/public /app/frontend/public
COPY --from=frontend /app/frontend/package.json /app/frontend/package.json
COPY --from=frontend /app/frontend/package-lock.json /app/frontend/package-lock.json
COPY --from=frontend /app/frontend/node_modules /app/frontend/node_modules

WORKDIR /app/backend
RUN python3 -m pip install --no-cache-dir .
RUN python3 -m playwright install chromium

EXPOSE 3000
EXPOSE 8000

CMD ["sh", "-lc", "cd /app/backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 & cd /app/frontend && npm run start -- --hostname 0.0.0.0 --port 3000"]
