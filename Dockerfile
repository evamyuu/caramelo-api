FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /srv
COPY pyproject.toml ./
# Install the browser that matches the installed Playwright version (pip may pick a newer one than the image).
RUN pip install --no-cache-dir . && playwright install chromium
COPY app ./app
COPY demo_sites ./demo_sites
COPY scripts ./scripts
USER pwuser
EXPOSE 8000
# Hosting platforms (Render) pass the port in $PORT; 8000 locally and in docker compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
