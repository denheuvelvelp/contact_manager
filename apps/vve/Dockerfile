FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY apps/vve/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/ /app/apps/

EXPOSE 8080

CMD exec uvicorn apps.vve.main:app --host 0.0.0.0 --port ${PORT:-8080}

