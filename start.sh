#!/bin/bash

# Set up directory permissions
echo "Setting up NGINX directories and permissions..."
mkdir -p /var/log/nginx
mkdir -p /var/lib/nginx/body
mkdir -p /var/lib/nginx/fastcgi
mkdir -p /var/lib/nginx/proxy
mkdir -p /var/lib/nginx/scgi
mkdir -p /var/lib/nginx/uwsgi
mkdir -p /mnt/data

touch /var/log/cron.log
chmod 666 /var/log/cron.log

# Create and set permissions for record log
touch /var/log/nginx/record.log
chmod 777 /var/log/nginx/record.log

# Set permissions
chown -R nobody:nogroup /var/log/nginx
chown -R nobody:nogroup /var/lib/nginx
chmod -R 755 /var/lib/nginx
chmod -R 755 /var/log/nginx
chmod -R 777 /mnt/data

# Start cron service
service cron start
echo "Started cron service"

# Check if NGINX RTMP module exists
echo "Checking for NGINX RTMP module..."
ls -l /usr/lib/nginx/modules/ngx_rtmp_module.so

# Verify NGINX configuration
echo "Testing NGINX configuration..."
nginx -t

# Start nginx
echo "Starting NGINX..."
nginx

# Show NGINX error log if it fails
if [ $? -ne 0 ]; then
    echo "NGINX failed to start. Error log:"
    cat /var/log/nginx/error.log
    exit 1
fi

# Start cron service for file mover and cleanup
echo "Setting up cron jobs for file mover and cleanup..."
# Run file mover every minute for organizing
echo "*/1 * * * * cd /app/app && python3 file_mover.py >> /var/log/cron.log 2>&1" > /etc/cron.d/move_files
# Also run a dedicated cleanup job at 1am
echo "0 1 * * * cd /app/app && python3 -c 'from file_mover import cleanup_old_recordings; cleanup_old_recordings()' >> /var/log/cron.log 2>&1" > /etc/cron.d/cleanup_files
chmod 0644 /etc/cron.d/move_files
chmod 0644 /etc/cron.d/cleanup_files
crontab /etc/cron.d/move_files
crontab -l | cat - /etc/cron.d/cleanup_files | crontab -
service cron start
echo "Cron service started."

# Start the Python NVR application in the background
echo "Starting NVR application..."
python3 -m app.main &

# Start the Flask web interface
echo "Starting web interface..."
python3 -m app.web