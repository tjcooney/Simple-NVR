FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Create nginx and HLS directories
RUN mkdir -p /etc/nginx/modules && \
    mkdir -p /var/log/nginx && \
    mkdir -p /var/lib/nginx && \
    mkdir -p /var/www/hls

# Install required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    nginx \
    libnginx-mod-rtmp \
    iputils-ping \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set proper permissions
RUN chown -R www-data:www-data /var/log/nginx && \
    chown -R www-data:www-data /var/lib/nginx && \
    chown -R www-data:www-data /etc/nginx && \
    chown -R www-data:www-data /var/www/hls

# Create app directory
WORKDIR /app

# Create data directory for SQLite database
RUN mkdir -p /data && \
    chown -R www-data:www-data /data && \
    chmod 777 /data

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy application code
COPY app/ ./app/

# Make sure PYTHONPATH includes the app directory
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Create necessary RTMP directories and set permissions
RUN mkdir -p /var/www/hls && \
    chown -R www-data:www-data /var/www && \
    chmod 777 /var/www/hls

# Expose ports
EXPOSE 1935
EXPOSE 80
EXPOSE 5001

# Copy and set permissions for startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]