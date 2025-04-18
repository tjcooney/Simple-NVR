# app/main.py

import asyncio
import signal
import logging
from app.database import init_db, Camera
from app.stream_manager import StreamManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Initialize database
        logger.info("Initializing database connection...")
        session = init_db()
        
        # Create stream manager
        logger.info("Creating stream manager...")
        stream_manager = StreamManager()
        
        # Get all cameras from database
        logger.info("Fetching cameras from database...")
        cameras = session.query(Camera).all()
        logger.info(f"Found {len(cameras)} cameras in database: {[camera.name for camera in cameras]}")
        
        # Start streams for all cameras
        for camera in cameras:
            try:
                logger.info(f"Starting processing for camera: {camera.name}")
                
                # Log the details of the camera
                logger.info(f"Camera details: Name={camera.name}, URL={camera.stream_url}")
                
                # Start the stream
                logger.info(f"Attempting to start stream for camera: {camera.name}")
                await stream_manager.start_stream(camera)
                
                # Confirm the stream was started successfully
                logger.info(f"Successfully started stream for camera: {camera.name}")
                
                # Add a delay between starting streams
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error processing camera {camera.name}: {e}", exc_info=True)
                continue

        logger.info("Finished processing all cameras.")
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal")
            asyncio.create_task(cleanup(stream_manager))
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the program running and monitor streams
        while True:
            # Log status of all streams
            for camera in cameras:
                if camera.name in stream_manager.processes:
                    process = stream_manager.processes[camera.name]
                    if process.poll() is not None:
                        logger.error(f"Stream {camera.name} has stopped with code {process.returncode}")
                        # Attempt to restart the stream
                        logger.info(f"Attempting to restart stream {camera.name}")
                        await stream_manager.start_stream(camera)
                else:
                    logger.warning(f"No process found for {camera.name}, attempting to start")
                    await stream_manager.start_stream(camera)
            
            await asyncio.sleep(10)  # Check every 10 seconds
            
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}", exc_info=True)
        raise


async def cleanup(stream_manager):
    logger.info("Starting cleanup...")
    await stream_manager.stop_all_streams()
    logger.info("Cleanup completed")
    exit(0)

if __name__ == "__main__":
    asyncio.run(main())