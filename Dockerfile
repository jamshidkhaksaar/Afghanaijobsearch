
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# We need wget/curl to download Chrome, and gnupg for keys
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Expose port (Render sets PORT env var)
EXPOSE 8501

# Enable headless mode for Selenium
ENV HEADLESS_MODE=true

# Healthcheck (will fail if PORT is not 8501, but that's okay for internal check or we can adjust)
# On Render, healthchecks are usually done via HTTP request config, but Docker healthcheck is fine.
# We'll rely on shell expansion for the port in CMD.

# Entrypoint using shell form to allow variable expansion
CMD sh -c "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"
