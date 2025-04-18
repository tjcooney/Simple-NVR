# Simple-NVR
I didn't like the NVR's that were available publically so I made my home with gstreamer and nginx backbone. It should work with RTSP streams from any camera manufacturer. Still working on stability and security, but it works.

## Setup & Configuration

1. Copy `env.example` to `.env` and update the following:
   - Set a secure password for the UI (`WEBSITE_PASSWORD`)
   - Configure where recordings are stored (`RECORDINGS_PATH`)
   - Set how long to keep recordings (`RETENTION_DAYS`, default is 7 days)
   - Set your timezone (`TZ`)

2. Use docker compose to build and run the application:
   ```
   docker-compose up -d
   ```

3. Access the web interface at `http://your-server-ip:5001`

## Features

- Support for RTSP camera streams
- Automatic organization of video recordings
- Automatic cleanup of old recordings (configured via `RETENTION_DAYS`)
- User-friendly web interface for managing and viewing camera streams