# Simple-NVR
I didn't like the NVR's that were available publically so I made my home with gstreamer and nginx backbone. It should work with RTSP streams from any camera manufacturer. Still working on stability and security, but it works.

Use docker compose to build and run this. Make sure you update the .env file to save the recordings in the right directory and set a login password for the UI.