FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Chrome
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libdrm2 \
    libgbm1 \
    libxshmfence1 \
    xdg-utils \
    gcc \
    libpq-dev \
    python3-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Add Google Chrome’s signing key and repository
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable=124.0.6367.91-1 && \
    rm -rf /var/lib/apt/lists/*

# Install matching Chromedriver
ENV CHROMEDRIVER_VERSION=124.0.6367.91
RUN wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/*

# Copy code
COPY backend/ .
COPY frontend/ ../frontend/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set port and run the app with gunicorn
ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
