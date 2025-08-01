FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget unzip gnupg ca-certificates \
    xvfb chromium-driver \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libgbm1 libxshmfence1 xdg-utils \
    fonts-liberation gcc libpq-dev python3-dev --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Chromium 122.0.6261.94 explicitly
RUN wget -q https://github.com/macchrome/linux-build/releases/download/v122.0.6261.94-r1173666/chromium-browser-snapshots-linux-x64.zip && \
    unzip chromium-browser-snapshots-linux-x64.zip && \
    mv chrome-linux /opt/chromium && \
    ln -s /opt/chromium/chrome /usr/bin/chromium && \
    rm chromium-browser-snapshots-linux-x64.zip

# Install matching ChromeDriver
RUN wget -q https://storage.googleapis.com/chromedriver/122.0.6261.94/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Set display for Xvfb
ENV DISPLAY=:99
ENV PORT=8080

# Copy project files
COPY backend/ .
COPY frontend/ ../frontend/

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Start server with Xvfb for non-headless browser automation
CMD xvfb-run --server-args="-screen 0 1920x1080x24" gunicorn --bind :$PORT --workers 1 --threads 8 app:app
