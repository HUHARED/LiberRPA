FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM haproxy:3.2.26-trixie AS proxy

FROM python:3.13-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIBERRPA_CONSOLE_CONFIG=/data/config/Console.jsonc \
    DJANGO_SETTINGS_MODULE=console_project.settings \
    PYTHONPATH=/app/backend \
    PATH=/usr/lib/postgresql/17/bin:$PATH

# Do not start Debian package services while building the image.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod +x /usr/sbin/policy-rc.d \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-17 postgresql-client-17 nginx-light \
        liblua5.4-0 libpcre2-8-0 libssl3t64 ca-certificates \
    && rm -rf /var/lib/apt/lists/* /var/lib/postgresql/17/main \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin liberrpa
COPY --from=proxy /usr/local/sbin/haproxy /usr/local/sbin/haproxy
RUN haproxy -vv && postgres --version && pg_dump --version

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY deployment/ ./deployment/
COPY *.py ./
COPY --from=frontend /build/dist/ /app/static/
RUN haproxy -c -f /app/deployment/haproxy.cfg

EXPOSE 52100
ENTRYPOINT ["python", "/app/deployment/runtime.py"]
CMD ["serve"]
