FROM python:3.11-slim

WORKDIR /app

# Install necessary system dependencies (incl. Xvfb + Chrome deps)
RUN apt-get update && apt-get install -y \
    wget unzip gnupg ca-certificates xvfb \
    fonts-liberation libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libdrm2 libgbm1 \
    libxshmfence1 xdg-utils gcc libpq-dev python3-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install specific version of Google Chrome
RUN wget https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_124.0.6367.91-1_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_124.0.6367.91-1_amd64.deb && \
    rm google-chrome-stable_124.0.6367.91-1_amd64.deb && \
    rm -rf /var/lib/apt/lists/*

# Install matching ChromeDriver
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/124.0.6367.91/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/*

# Copy application files
COPY backend/ .
COPY frontend/ ../frontend/

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Set display environment variable for pyvirtualdisplay/Xvfb
ENV DISPLAY=:99
ENV PORT=8080

# Start the application
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
