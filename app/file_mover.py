import os
import shutil
from datetime import datetime, timedelta

RECORDINGS_FOLDER = "/mnt/data"

def move_video_files():
    now = datetime.now()
    threshold_time = now - timedelta(minutes=11)

    for filename in os.listdir(RECORDINGS_FOLDER):
        if filename.endswith('.flv'):
            try:
                # Split filename based on underscores and parse camera name dynamically
                parts = filename.rsplit('_', 2)  # Split only at the last two underscores
                if len(parts) != 3:
                    print(f"Skipping file due to unexpected format: {filename}")
                    continue
                
                camera_name = parts[0]  # All characters before the last two underscores
                date_str = parts[1]
                time_str = parts[2].replace('.flv', '')

                # Debug log
                print(f"Processing file: {filename}, Camera: {camera_name}")

                file_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                
                if file_datetime < threshold_time:
                    date_folder = os.path.join(RECORDINGS_FOLDER, date_str)
                    camera_folder = os.path.join(date_folder, camera_name)
                    os.makedirs(camera_folder, exist_ok=True)

                    src_path = os.path.join(RECORDINGS_FOLDER, filename)
                    dest_path = os.path.join(camera_folder, filename)
                    shutil.move(src_path, dest_path)
                    print(f"Moved: {filename} -> {dest_path}")
            except Exception as e:
                print(f"Error processing file {filename}: {e}")

if __name__ == "__main__":
    move_video_files()
