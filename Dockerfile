FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including xvfb and Chromium
RUN apt-get update && apt-get install -y \
    xvfb chromium-driver chromium \
    wget unzip ca-certificates libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libdrm2 libgbm1 libxshmfence1 \
    xdg-utils fonts-liberation gcc libpq-dev python3-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install ChromeDriver matching Chromium
RUN CHROME_VERSION=$(chromium --version | grep -oP "\d+\.\d+\.\d+") && \
    echo "Chromium version: $CHROME_VERSION" && \
    wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION" && \
    wget -O /tmp/chromedriver_full.zip "https://chromedriver.storage.googleapis.com/${CHROME_VERSION}/chromedriver_linux64.zip" || true && \
    unzip -o /tmp/chromedriver_full.zip -d /usr/local/bin/ || true && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/*

ENV DISPLAY=:99
ENV PORT=8080

# Copy app files
COPY backend/ .
COPY frontend/ ../frontend/

RUN pip install --no-cache-dir -r requirements.txt

CMD xvfb-run --server-args="-screen 0 1920x1080x24" gunicorn --bind :$PORT --workers 1 --threads 8 app:app
