FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev python3-dev

COPY backend/ .
COPY frontend/ ../frontend/

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app