import os
import shutil
import time
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Source directory for recordings
RECORDINGS_FOLDER = "/mnt/data"

def get_retention_days():
    """Get retention days from environment or use default value of 7"""
    try:
        return int(os.environ.get('RETENTION_DAYS', 7))
    except (ValueError, TypeError):
        logger.warning("Invalid RETENTION_DAYS value, using default of 7 days")
        return 7

def organize_video_files():
    """Organize video files into date-based folders by camera name"""
    now = datetime.now()
    threshold_time = now - timedelta(minutes=11)  # Files older than 11 minutes
    
    # Create directory if it doesn't exist
    if not os.path.exists(RECORDINGS_FOLDER):
        os.makedirs(RECORDINGS_FOLDER, exist_ok=True)
        logger.info(f"Created recordings folder: {RECORDINGS_FOLDER}")
    
    for filename in os.listdir(RECORDINGS_FOLDER):
        if filename.endswith('.flv'):
            try:
                # Format appears to be "CameraName-timestamp.flv"
                if '-' not in filename:
                    logger.warning(f"Skipping file due to unexpected format (no hyphen): {filename}")
                    continue
                
                # Split by hyphen to separate camera name and timestamp
                parts = filename.split('-', 1)
                if len(parts) != 2:
                    logger.warning(f"Skipping file due to unexpected format: {filename}")
                    continue
                
                camera_name = parts[0]
                timestamp_str = parts[1].replace('.flv', '')
                
                logger.debug(f"Processing file: {filename}, Camera: {camera_name}, Timestamp: {timestamp_str}")
                
                # Convert timestamp to datetime
                try:
                    # Unix timestamp format
                    timestamp = int(timestamp_str)
                    file_datetime = datetime.fromtimestamp(timestamp)
                except ValueError:
                    logger.warning(f"Could not parse timestamp from filename: {filename}")
                    continue
                
                # Format the date as YYYY-MM-DD for folder structure
                date_str = file_datetime.strftime("%Y-%m-%d")
                
                # Only move files older than threshold
                if file_datetime < threshold_time:
                    # Create date folder if it doesn't exist
                    date_folder = os.path.join(RECORDINGS_FOLDER, date_str)
                    os.makedirs(date_folder, exist_ok=True)
                    
                    # Create camera folder inside date folder
                    camera_folder = os.path.join(date_folder, camera_name)
                    os.makedirs(camera_folder, exist_ok=True)
                    
                    # Move the file
                    src_path = os.path.join(RECORDINGS_FOLDER, filename)
                    dest_path = os.path.join(camera_folder, filename)
                    shutil.move(src_path, dest_path)
                    logger.info(f"Moved: {filename} -> {dest_path}")
            except Exception as e:
                logger.error(f"Error processing file {filename}: {e}", exc_info=True)

def cleanup_old_recordings():
    """Delete recordings older than the specified retention period"""
    retention_days = get_retention_days()
    logger.info(f"Cleaning up recordings older than {retention_days} days")
    
    # Get current time and calculate threshold (X days ago)
    now = datetime.now()
    threshold_date = now - timedelta(days=retention_days)
    threshold_timestamp = threshold_date.timestamp()
    
    logger.info(f"Current time: {now}, Threshold date: {threshold_date}")
    
    # Clean up files in the root recordings directory
    for filename in os.listdir(RECORDINGS_FOLDER):
        file_path = os.path.join(RECORDINGS_FOLDER, filename)
        
        # Skip directories (they'll be handled separately)
        if os.path.isdir(file_path):
            continue
            
        # Check if the file is a video file
        if filename.endswith('.flv'):
            try:
                file_age_days = 0
                file_create_time = None
                delete_file = False
                
                # Use creation/modification time for age calculation
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                file_age_days = (now - file_mtime).days
                
                # Log detailed info about the file for debugging
                logger.info(f"File: {filename}, Modification time: {file_mtime}, Age: {file_age_days} days")
                
                # Only delete if older than retention period
                if file_age_days >= retention_days:
                    logger.info(f"Deleting file {filename} - {file_age_days} days old (> {retention_days} days retention)")
                    os.remove(file_path)
                else:
                    logger.info(f"Keeping file {filename} - {file_age_days} days old (< {retention_days} days retention)")
                
            except Exception as e:
                logger.error(f"Error processing file {filename}: {e}", exc_info=True)
    
    # Clean up date directories older than retention period
    for date_dir in os.listdir(RECORDINGS_FOLDER):
        dir_path = os.path.join(RECORDINGS_FOLDER, date_dir)
        
        # Skip files and process only directories
        if not os.path.isdir(dir_path):
            continue
            
        try:
            # First try to determine directory age from its name (if it's in YYYY-MM-DD format)
            dir_age_days = 0
            try:
                # Try to parse date from directory name (format: YYYY-MM-DD)
                date_obj = datetime.strptime(date_dir, "%Y-%m-%d")
                dir_age_days = (now - date_obj).days
                logger.info(f"Directory: {date_dir}, Date from name: {date_obj}, Age: {dir_age_days} days")
            except ValueError:
                # If directory name is not a date, use modification time
                dir_mtime = datetime.fromtimestamp(os.path.getmtime(dir_path))
                dir_age_days = (now - dir_mtime).days
                logger.info(f"Directory: {date_dir}, Modification time: {dir_mtime}, Age: {dir_age_days} days")
            
            # Only delete if older than retention period
            if dir_age_days >= retention_days:
                logger.info(f"Deleting directory {date_dir} - {dir_age_days} days old (> {retention_days} days retention)")
                shutil.rmtree(dir_path)
            else:
                logger.info(f"Keeping directory {date_dir} - {dir_age_days} days old (< {retention_days} days retention)")
                
        except Exception as e:
            logger.error(f"Error processing directory {date_dir}: {e}", exc_info=True)

def main():
    """Main function to organize and clean up recordings"""
    logger.info("Starting file organization and cleanup")
    organize_video_files()
    cleanup_old_recordings()
    logger.info("Completed file organization and cleanup")

if __name__ == "__main__":
    main()
