# Gebruik officiële Python lightweight image
FROM python:3.11-slim

# Voorkom buffering voor directe Cloud Logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Installeer dependencies
COPY apps/cooperatie/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer applicatiecode
COPY apps/ /app/apps/

# Exposeer poort (Cloud Run gebruikt standaard 8080)
EXPOSE 8080

# Start Uvicorn server
CMD exec uvicorn apps.cooperatie.main:app --host 0.0.0.0 --port ${PORT:-8080}

