#!/bin/bash

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

# Start the Python NVR application in the background
echo "Starting NVR application..."
python3 -m app.main &

# Start the Flask web interface
echo "Starting web interface..."
python3 -m app.web