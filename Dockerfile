FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    fonts-liberation libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libdrm2 libgbm1 \
    libxshmfence1 xdg-utils gcc libpq-dev python3-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Add Google’s signing key (modern method) and Chrome repo
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /etc/apt/keyrings/google-linux.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list

# Install specific version of Chrome and matching Chromedriver
RUN apt-get update && \
    apt-get install -y google-chrome-stable=124.0.6367.91-1 && \
    wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/124.0.6367.91/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/* /var/lib/apt/lists/*

# Copy project files
COPY backend/ .
COPY frontend/ ../frontend/

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
