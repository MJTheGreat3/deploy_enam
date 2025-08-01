FROM python:3.11-slim

WORKDIR /app

# 1. Install system deps, Xvfb, Chromium, and Chromium-driver
RUN apt-get update && apt-get install -y \
    xvfb chromium chromium-driver \
    wget unzip ca-certificates libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libdrm2 libgbm1 libxshmfence1 \
    xdg-utils fonts-liberation gcc libpq-dev python3-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 2. Copy application files
COPY backend/ .
COPY frontend/ ../frontend/

# 3. Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# 4. Configure environment and start app under Xvfb
ENV DISPLAY=:99
ENV PORT=8080
CMD xvfb-run --server-args="-screen 0 1920x1080x24" \
    gunicorn --bind :$PORT --workers 1 --threads 8 app:app
