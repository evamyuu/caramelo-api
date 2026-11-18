FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /srv
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY app ./app
COPY demo_sites ./demo_sites
USER pwuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
