FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV RETENTION_DAYS=7

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
    cron \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create all required directories
RUN mkdir -p /etc/nginx/modules \
    /var/log/nginx \
    /var/lib/nginx \
    /var/www/hls \
    /data \
    /mnt/data \
    /app \
    /tmp/nginx \
    /var/lib/nginx/body \
    /var/lib/nginx/fastcgi \
    /var/lib/nginx/proxy \
    /var/lib/nginx/scgi \
    /var/lib/nginx/uwsgi

# Set directory ownership and permissions
RUN chown -R nobody:nogroup /var/log/nginx \
    /var/lib/nginx \
    /etc/nginx \
    /var/www \
    /data \
    /mnt/data \
    /tmp/nginx && \
    chmod -R 755 /var/log/nginx \
    /var/lib/nginx \
    /etc/nginx \
    /var/www && \
    chmod 777 /var/www/hls \
    /data \
    /mnt/data \
    /tmp/nginx

# Create cleanup script
RUN <<'EOF' cat > /cleanup.sh
#!/bin/bash
# Find and remove directories older than ${RETENTION_DAYS} days in /mnt/data
find /mnt/data -mindepth 1 -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
# Find and remove directories older than ${RETENTION_DAYS} days in /data
find /data -mindepth 1 -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
# Log the cleanup
echo "$(date): Cleanup completed for files older than ${RETENTION_DAYS} days" >> /var/log/cleanup.log
EOF

RUN chmod +x /cleanup.sh

# Add cleanup job to crontab - run at 1am
RUN echo "0 1 * * * /cleanup.sh >> /var/log/cron.log 2>&1" > /etc/cron.d/cleanup-recordings && \
    chmod 0644 /etc/cron.d/cleanup-recordings && \
    crontab /etc/cron.d/cleanup-recordings

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Copy nginx configuration and set permissions
COPY nginx.conf /etc/nginx/nginx.conf
RUN chown nobody:nogroup /etc/nginx/nginx.conf && \
    chmod 644 /etc/nginx/nginx.conf

# Copy application code
COPY app/ ./app/
RUN chown -R nobody:nogroup /app

# Copy and set permissions for startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

ENV PYTHONPATH="/app:${PYTHONPATH}"

EXPOSE 1935 80 5001

CMD ["/start.sh"]