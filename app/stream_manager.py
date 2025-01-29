# app/stream_manager.py
import asyncio
import logging
from subprocess import Popen, PIPE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self):
        self.processes = {}

    def create_gst_command(self, camera):
        try:
            # Log that command creation is starting
            logger.info(f"Creating GStreamer command for camera: {camera.name}")
            
            # Construct the RTSP URL
            if camera.username and camera.password:
                rtsp_url = f"rtsp://{camera.username}:{camera.password}@{camera.stream_url}"
            else:
                rtsp_url = f"rtsp://{camera.stream_url}"
            
            # Log the constructed RTSP URL
            logger.info(f"RTSP URL for {camera.name}: {rtsp_url}")
            
            # Construct the full GStreamer command
            command = f'gst-launch-1.0 -v rtspsrc location="{rtsp_url}" do-rtsp-keep-alive=true protocols=tcp retry=10 latency=100 timeout=50000000 ! rtph264depay ! h264parse ! flvmux ! rtmpsink sync=false location="rtmp://127.0.0.1/live/{camera.name}"'
            
            # Log the generated command
            logger.info(f"Generated GStreamer command for {camera.name}: {command}")
            return command
        except Exception as e:
            # Log any exceptions that occur during command creation
            logger.error(f"Error creating GStreamer command for camera {camera.name}: {str(e)}", exc_info=True)
            raise

    async def start_stream(self, camera):
        logger.info(f"Start stream called for camera: {camera.name}")
        
        if camera.name in self.processes:
            logger.warning(f"Stream {camera.name} is already running")
            return

        try:
            logger.info(f"Generating command for camera: {camera.name}")
            command = self.create_gst_command(camera)
            logger.info(f"Command generated for {camera.name}: {command}")
            
            process = Popen(
                command,
                stdout=PIPE,
                stderr=PIPE,
                shell=True,
                text=True,
                bufsize=1
            )
            self.processes[camera.name] = process
            
            logger.info(f"Process started for camera: {camera.name}")
            asyncio.create_task(self._monitor_process(camera.name, process))
        except Exception as e:
            logger.error(f"Failed to start stream for camera {camera.name}: {e}", exc_info=True)
            if camera.name in self.processes:
                del self.processes[camera.name]



    async def _monitor_process(self, camera_name, process):
        """Simplified process monitoring for a camera."""
        logger.info(f"Monitoring process for camera: {camera_name}")

        try:
            while True:
                line = process.stdout.readline()
                if line:
                    logger.info(f"{camera_name} OUT: {line.strip()}")

                # Exit the loop if the process has ended
                if process.poll() is not None:
                    break

                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error monitoring camera {camera_name}: {e}", exc_info=True)
        finally:
            return_code = process.poll()
            logger.info(f"Process for {camera_name} exited with code {return_code}")
            if camera_name in self.processes:
                del self.processes[camera_name]
        def check_streams(self):
            """Check the status of all streams"""
            status = {}
            for name, process in self.processes.items():
                if process.poll() is None:
                    status[name] = "running"
                else:
                    status[name] = f"stopped (exit code: {process.returncode})"
            return status

    async def stop_stream(self, camera_name):
        if camera_name in self.processes:
            process = self.processes[camera_name]
            logger.info(f"Stopping stream: {camera_name}")
            process.terminate()
            await asyncio.sleep(1)
            if process.poll() is None:
                logger.warning(f"Stream {camera_name} did not terminate gracefully, forcing kill")
                process.kill()
            stdout, stderr = process.communicate()
            logger.info(f"Stream {camera_name} stopped. Exit code: {process.returncode}")
            if stderr:
                logger.info(f"Final output: {stderr}")
            del self.processes[camera_name]

    async def stop_all_streams(self):
        logger.info("Stopping all streams...")
        for camera_name in list(self.processes.keys()):
            await self.stop_stream(camera_name)
        logger.info("All streams stopped")