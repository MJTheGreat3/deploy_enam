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

# Install specific version of Chrome manually
RUN wget https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_124.0.6367.91-1_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_124.0.6367.91-1_amd64.deb && \
    rm google-chrome-stable_124.0.6367.91-1_amd64.deb

# Install matching ChromeDriver
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/124.0.6367.91/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/*

# Copy project files
COPY backend/ .
COPY frontend/ ../frontend/

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
