FROM mcr.microsoft.com/playwright/python:v1.48.0-noble
WORKDIR /srv
COPY pyproject.toml ./
# Ubuntu 24.04 image (Python 3.12). Install the browser that matches the installed Playwright version.
RUN pip install --no-cache-dir --break-system-packages . && playwright install chromium
COPY app ./app
COPY demo_sites ./demo_sites
COPY scripts ./scripts
USER pwuser
EXPOSE 8000
# Hosting platforms (Render) pass the port in $PORT; 8000 locally and in docker compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
