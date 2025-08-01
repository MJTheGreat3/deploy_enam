FROM python:3.11-slim

WORKDIR /app

# Install required dependencies
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
    --no-install-recommends

# Add Google Chrome signing key and repository
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Install Google Chrome
RUN apt-get update && apt-get install -y google-chrome-stable

# Get Chrome version and download corresponding Chromedriver
RUN CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+') && \
    echo "Detected Chrome version: $CHROME_VERSION" && \
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION") && \
    echo "Installing Chromedriver version: $CHROMEDRIVER_VERSION" && \
    wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/*

# Set environment variables for Selenium
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER=/usr/local/bin/chromedriver

# Copy code
COPY backend/ .
COPY frontend/ ../frontend/

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
