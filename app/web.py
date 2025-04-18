from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
import requests
from dotenv import load_dotenv
import os
import logging
import glob
import re
from datetime import datetime, date, timedelta
import subprocess
import base64
from pathlib import Path
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user 
from .database import init_db, Camera
from werkzeug.security import generate_password_hash, check_password_hash

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-default-secret-key')
app.config['WEBSITE_TITLE'] = os.getenv('WEBSITE_TITLE', 'Default Title')
app.config['PASSWORD_HASH'] = generate_password_hash(os.getenv('WEBSITE_PASSWORD', 'defaultpassword'))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        if check_password_hash(app.config['PASSWORD_HASH'], password):
            user = User(1)
            login_user(user, remember=remember, duration=timedelta(days=30))
            flash('You are now logged in.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.context_processor
def inject_cameras():
    """Make cameras list available to all templates"""
    session = init_db()
    cameras = session.query(Camera).all()
    return dict(cameras=cameras)

@app.route('/')
@login_required
def index():
    return render_template('index.html', 
                         title=app.config['WEBSITE_TITLE'])

@app.route('/add_camera', methods=['GET', 'POST'])
@login_required
def add_camera():
    if request.method == 'POST':
        name = request.form['name']
        stream_url = request.form['stream_url']
        username = request.form['username'] if request.form['username'] else None
        password = request.form['password'] if request.form['password'] else None

        try:
            session = init_db()
            camera = Camera(
                name=name,
                stream_url=stream_url,
                username=username,
                password=password
            )
            session.add(camera)
            session.commit()
            flash('Camera added successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error adding camera: {str(e)}', 'error')
            return redirect(url_for('add_camera'))

    return render_template('add_camera.html')

@app.route('/edit_camera/<int:camera_id>', methods=['GET', 'POST'])
@login_required
def edit_camera(camera_id):
    session = init_db()
    camera = session.query(Camera).filter_by(id=camera_id).first()

    if not camera:
        flash('Camera not found.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Update camera details with form data
        camera.name = request.form['name']
        camera.stream_url = request.form['stream_url']
        camera.username = request.form.get('username', None)
        camera.password = request.form.get('password', None)

        try:
            session.commit()
            flash('Camera details updated successfully!', 'success')
        except Exception as e:
            session.rollback()
            flash(f'Error updating camera details: {str(e)}', 'error')

        return redirect(url_for('view_camera', camera_id=camera.id))

    return render_template('edit_camera.html', camera=camera)

@app.route('/delete_camera/<int:camera_id>', methods=['POST'])
@login_required
def delete_camera(camera_id):
    try:
        session = init_db()
        camera = session.query(Camera).filter_by(id=camera_id).first()
        if camera:
            session.delete(camera)
            session.commit()
            flash('Camera deleted successfully!', 'success')
        else:
            flash('Camera not found.', 'error')
    except Exception as e:
        flash(f'Error deleting camera: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/view_camera/<int:camera_id>')
@login_required
def view_camera(camera_id):
    session = init_db()
    camera = session.query(Camera).filter_by(id=camera_id).first()
    if not camera:
        flash('Camera not found.', 'error')
        return redirect(url_for('index'))
    return render_template(
        'view_camera.html', 
        camera=camera, 
        site_title=app.config['WEBSITE_TITLE'], 
        page_title=f"Viewing {camera.name}"
    )

@app.route('/debug')
def debug():
    debug_info = {
        'hls_directory': [],
        'rtmp_stats': '',
        'nginx_errors': '',
        'processes': {}
    }

    # Check HLS directory
    try:
        debug_info['hls_directory'] = os.listdir('/var/www/hls')
    except Exception as e:
        debug_info['hls_directory'] = f"Error listing HLS directory: {str(e)}"

    # Check NGINX RTMP stats
    try:
        rtmp_stats_response = requests.get('http://localhost/stat')
        debug_info['rtmp_stats'] = rtmp_stats_response.text
    except Exception as e:
        debug_info['rtmp_stats'] = f"Error getting RTMP stats: {str(e)}"

    # Check NGINX error log
    try:
        with open('/var/log/nginx/error.log', 'r') as f:
            debug_info['nginx_errors'] = f.read()
    except Exception as e:
        debug_info['nginx_errors'] = f"Error reading NGINX error log: {str(e)}"

    return jsonify(debug_info)

@app.route('/stream_status')
def stream_status():
    session = init_db()
    cameras = session.query(Camera).all()
    
    status = {}
    for camera in cameras:
        # Check HLS file existence
        m3u8_path = f'/var/www/hls/{camera.name}.m3u8'
        ts_files = []
        
        try:
            if os.path.exists(m3u8_path):
                status[camera.name] = {
                    'hls_playlist': True,
                    'last_modified': os.path.getmtime(m3u8_path)
                }
                # Look for TS segments
                for file in os.listdir('/var/www/hls'):
                    if file.startswith(camera.name) and file.endswith('.ts'):
                        ts_files.append(file)
                status[camera.name]['ts_segments'] = ts_files
            else:
                status[camera.name] = {
                    'hls_playlist': False,
                    'error': 'No HLS playlist found'
                }
        except Exception as e:
            status[camera.name] = {
                'error': f'Error checking stream: {str(e)}'
            }
    
    return jsonify(status)

# Log environment variables at startup
print("\n----- ENVIRONMENT VARIABLES -----")
print(f"RECORDINGS_PATH: {os.getenv('RECORDINGS_PATH', '(not set)')}")
print(f"PWD: {os.getcwd()}")
print(f"PYTHONPATH: {os.getenv('PYTHONPATH', '(not set)')}")
print(f"User: {os.getenv('USER', '(not set)')}")
print("--------------------------------\n")

# Check recordings directory on startup
recordings_path = os.getenv('RECORDINGS_PATH', '/mnt/data')
if not os.path.isabs(recordings_path):
    recordings_path = os.path.join(os.getcwd(), recordings_path)

print(f"\n----- CHECKING RECORDINGS DIRECTORY: {recordings_path} -----")
if os.path.exists(recordings_path):
    print(f"Directory exists, listing content:")
    for item in os.listdir(recordings_path):
        item_path = os.path.join(recordings_path, item)
        item_type = "directory" if os.path.isdir(item_path) else "file"
        item_size = os.path.getsize(item_path) if os.path.isfile(item_path) else "-"
        print(f"  - {item} ({item_type}, {item_size} bytes)")
    
    # Check for .flv files
    flv_files = [f for f in os.listdir(recordings_path) if f.endswith('.flv')]
    print(f"\nFound {len(flv_files)} .flv files:")
    for flv in flv_files[:5]:  # Show only first 5
        print(f"  - {flv}")
    if len(flv_files) > 5:
        print(f"  ... and {len(flv_files) - 5} more")
else:
    print(f"Directory does not exist!")
print("--------------------------------\n")

# Recording browser functionality
@app.route('/recordings')
@login_required
def recordings_browser():
    """Main recordings browser page with calendar view"""
    session = init_db()
    cameras = session.query(Camera).all()
    
    # Get available dates with recordings
    recording_dates = get_available_dates()
    
    # Default to today or most recent date with recordings
    selected_date = request.args.get('date')
    if selected_date:
        try:
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()
        
    # Generate calendar data for the current month
    calendar_data = generate_calendar_data(selected_date, recording_dates)
    
    return render_template(
        'recordings.html',
        cameras=cameras,
        calendar_data=calendar_data,
        selected_date=selected_date,
        available_dates=recording_dates,
        site_title=app.config['WEBSITE_TITLE'],
        page_title="Recordings Browser"
    )

@app.route('/recordings/<camera_name>')
@login_required
def camera_recordings(camera_name):
    """View recordings for a specific camera"""
    session = init_db()
    camera = session.query(Camera).filter_by(name=camera_name).first()
    
    if not camera:
        flash('Camera not found.', 'error')
        return redirect(url_for('recordings_browser'))
    
    # Get date from query params or default to today
    requested_date = request.args.get('date')
    try:
        if requested_date:
            selected_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
        else:
            selected_date = date.today()
    except ValueError:
        selected_date = date.today()
    
    # Get recordings for this camera on the selected date
    recordings_list = get_recordings_by_date(camera_name, selected_date)
    
    # Get available dates with recordings for this camera
    available_dates = get_available_dates(camera_name)
    
    # Generate calendar data
    calendar_data = generate_calendar_data(selected_date, available_dates)
    
    return render_template(
        'camera_recordings.html',
        camera=camera,
        recordings=recordings_list,
        selected_date=selected_date,
        calendar_data=calendar_data,
        available_dates=available_dates,
        site_title=app.config['WEBSITE_TITLE'],
        page_title=f"Recordings - {camera.name}"
    )

@app.route('/api/recordings')
@login_required
def api_recordings_list():
    """API endpoint to get recordings data"""
    camera_name = request.args.get('camera')
    date_str = request.args.get('date')
    
    try:
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            selected_date = date.today()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    
    if camera_name:
        # Get recordings for specific camera
        recordings = get_recordings_by_date(camera_name, selected_date)
        return jsonify({
            'camera': camera_name,
            'date': date_str,
            'recordings': recordings
        })
    else:
        # Get recordings for all cameras
        result = {}
        session = init_db()
        cameras = session.query(Camera).all()
        
        for camera in cameras:
            result[camera.name] = get_recordings_by_date(camera.name, selected_date)
        
        return jsonify({
            'date': date_str,
            'cameras': result
        })

@app.route('/recording/<path:file_path>')
@login_required
def serve_recording(file_path):
    """Serve a recording file"""
    recordings_dir = os.getenv('RECORDINGS_PATH', '/mnt/data')
    # Handle relative paths (default to current directory)
    if not os.path.isabs(recordings_dir):
        recordings_dir = os.path.join(os.getcwd(), recordings_dir)
    full_path = os.path.join(recordings_dir, file_path)
    
    # Security check to prevent directory traversal
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        flash('Recording not found', 'error')
        return redirect(url_for('recordings_browser'))
    
    if not full_path.startswith(os.path.abspath(recordings_dir)):
        return "Access denied", 403
    
    # Determine the content type based on file extension
    content_type = "video/x-flv"  # Default for .flv files
    
    # Serve the file using Flask's send_file
    return send_file(full_path, mimetype=content_type)

@app.route('/api/recording/thumbnail')
@login_required
def api_recording_thumbnail():
    """Generate and serve a thumbnail for a recording"""
    recording_path = request.args.get('path')
    
    if not recording_path:
        return jsonify({'error': 'No recording path provided'}), 400
    
    # For security, make sure we're only accessing files in the recordings directory
    recordings_dir = os.getenv('RECORDINGS_PATH', '/mnt/data')
    # Handle relative paths (default to current directory)
    if not os.path.isabs(recordings_dir):
        recordings_dir = os.path.join(os.getcwd(), recordings_dir)
    full_path = os.path.join(recordings_dir, recording_path.lstrip('/'))
    
    if not os.path.exists(full_path) or not full_path.startswith(recordings_dir):
        return jsonify({'error': 'Recording not found or access denied'}), 404
    
    try:
        # Generate thumbnail using ffmpeg
        thumbnail = generate_thumbnail(full_path)
        return jsonify({'thumbnail': thumbnail})
    except Exception as e:
        return jsonify({'error': f'Failed to generate thumbnail: {str(e)}'}), 500

@app.route('/api/calendar')
@login_required
def api_calendar_data():
    """API endpoint to get calendar data with recording availability"""
    month = request.args.get('month')
    year = request.args.get('year')
    camera_name = request.args.get('camera')
    
    try:
        if month and year:
            month = int(month)
            year = int(year)
            first_day = date(year, month, 1)
        else:
            first_day = date.today().replace(day=1)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid month or year'}), 400
    
    # Get available dates with recordings
    available_dates = get_available_dates(camera_name)
    
    # Generate calendar data
    calendar_data = generate_calendar_data(first_day, available_dates)
    
    return jsonify({
        'year': first_day.year,
        'month': first_day.month,
        'calendar': calendar_data
    })

def get_available_dates(camera_name=None):
    """Get list of dates with recordings available"""
    recordings_dir = os.getenv('RECORDINGS_PATH', '/mnt/data')
    print(f"DEBUG: Using recordings directory: {recordings_dir}")
    
    # Handle relative paths (default to current directory)
    if not os.path.isabs(recordings_dir):
        recordings_dir = os.path.join(os.getcwd(), recordings_dir)
        print(f"DEBUG: Updated to absolute path: {recordings_dir}")
    
    available_dates = set()
    
    # First check if recordings_dir exists
    if not os.path.exists(recordings_dir):
        print(f"Warning: Recordings directory {recordings_dir} does not exist")
        return []
    
    print(f"DEBUG: Listing contents of recordings directory {recordings_dir}:")
    for item in os.listdir(recordings_dir):
        item_path = os.path.join(recordings_dir, item)
        if os.path.isdir(item_path):
            print(f"  - Directory: {item}")
        else:
            print(f"  - File: {item} ({os.path.getsize(item_path)} bytes)")
            
    if camera_name:
        print(f"DEBUG: Filtering for camera: {camera_name}")
    
    # Check date directories directly in recordings folder (if we're using organized structure)
    try:
        for item in os.listdir(recordings_dir):
            item_path = os.path.join(recordings_dir, item)
            
            # If it's a date-formatted directory (try multiple formats)
            if os.path.isdir(item_path):
                # Try different date formats
                recording_date = None
                date_formats = ['%Y-%m-%d', '%Y%m%d', '%m-%d-%Y', '%d-%m-%Y']
                
                for date_format in date_formats:
                    try:
                        recording_date = datetime.strptime(item, date_format).date()
                        print(f"DEBUG: Found date directory with format {date_format}: {item}")
                        break  # Stop trying formats if we find a match
                    except ValueError:
                        continue
                        
                if recording_date:
                    # If camera name specified, check if that camera has recordings on this date
                    if camera_name:
                        camera_dir = os.path.join(item_path, camera_name)
                        if os.path.isdir(camera_dir) and any(f.endswith('.flv') for f in os.listdir(camera_dir)):
                            available_dates.add(recording_date)
                            print(f"DEBUG: Added date {recording_date} for camera {camera_name}")
                    else:
                        available_dates.add(recording_date)
                        print(f"DEBUG: Added date {recording_date} (all cameras)")
        
        # Check for recordings directly in the root directory
        for file in os.listdir(recordings_dir):
            if file.endswith('.flv'):
                file_path = os.path.join(recordings_dir, file)
                
                # Skip directories
                if os.path.isdir(file_path):
                    continue
                
                # If filtering by camera, skip files that don't match
                if camera_name and not file.startswith(camera_name):
                    continue
                
                try:
                    # If it has a timestamp in the filename (CameraName-timestamp.flv)
                    if '-' in file:
                        parts = file.split('-', 1)
                        if len(parts) == 2:
                            # Try to extract date from timestamp
                            timestamp_str = parts[1].replace('.flv', '')
                            timestamp = int(timestamp_str)
                            file_date = datetime.fromtimestamp(timestamp).date()
                            available_dates.add(file_date)
                    else:
                        # If we can't parse the filename, use file modification time
                        mtime = os.path.getmtime(file_path)
                        file_date = datetime.fromtimestamp(mtime).date()
                        available_dates.add(file_date)
                except (ValueError, IndexError) as e:
                    print(f"Error parsing date for {file}: {e}")
                    continue
    except Exception as e:
        print(f"Error scanning recordings directory: {e}")
    
    return sorted(list(available_dates))

def get_recordings_by_date(camera_name, selected_date):
    """Get list of recordings for a specific camera and date"""
    recordings_dir = os.getenv('RECORDINGS_PATH', '/mnt/data')
    print(f"DEBUG: Finding recordings for camera '{camera_name}' on date {selected_date}")
    
    # Handle relative paths (default to current directory)
    if not os.path.isabs(recordings_dir):
        recordings_dir = os.path.join(os.getcwd(), recordings_dir)
        print(f"DEBUG: Updated to absolute path: {recordings_dir}")
    
    recordings = []
    
    # Check if directory exists
    if not os.path.exists(recordings_dir):
        print(f"Warning: Recordings directory {recordings_dir} does not exist")
        return []
        
    print(f"DEBUG: Checking for recordings in {recordings_dir}")
    
    # Try different date formats for directories
    date_formats = ['%Y-%m-%d', '%Y%m%d', '%m-%d-%Y', '%d-%m-%Y']
    potential_date_dirs = []
    
    for date_format in date_formats:
        date_str = selected_date.strftime(date_format)
        date_dir = os.path.join(recordings_dir, date_str)
        if os.path.isdir(date_dir):
            print(f"DEBUG: Found matching date directory: {date_dir}")
            potential_date_dirs.append(date_dir)
    
    # Check all potential date directories
    for date_dir in potential_date_dirs:
        camera_dir = os.path.join(date_dir, camera_name)
        
        # Check organized recordings in date/camera directory (if they exist)
        if os.path.isdir(camera_dir):
            print(f"DEBUG: Found camera sub-directory: {camera_dir}")
            for file in os.listdir(camera_dir):
                if file.endswith('.flv'):
                    file_path = os.path.join(camera_dir, file)
                    recordings.append(get_recording_info(file, file_path, camera_name, recordings_dir))
                    print(f"DEBUG: Added organized recording: {file}")
    
    if not potential_date_dirs:
        print(f"DEBUG: No matching date directories found for date: {selected_date}")
    
    # Check for files directly in the recordings directory
    try:
        file_count = 0
        flv_count = 0
        matching_camera_count = 0
        matching_date_count = 0
        
        print(f"DEBUG: Scanning files in {recordings_dir}")
        
        for file in os.listdir(recordings_dir):
            file_count += 1
            if file.endswith('.flv'):
                flv_count += 1
                file_path = os.path.join(recordings_dir, file)
                print(f"DEBUG: Found FLV file: {file}")
                
                # Skip directories
                if os.path.isdir(file_path):
                    print(f"DEBUG: Skipping directory: {file}")
                    continue
                
                # Check if this file belongs to this camera
                if not file.startswith(camera_name):
                    print(f"DEBUG: File {file} doesn't match camera {camera_name}")
                    continue
                
                matching_camera_count += 1
                print(f"DEBUG: File {file} matches camera {camera_name}")
                
                # Try to determine if this recording is from the selected date
                try:
                    # If the file follows the naming pattern with timestamp
                    if '-' in file:
                        parts = file.split('-', 1)
                        if len(parts) == 2:
                            timestamp_str = parts[1].replace('.flv', '')
                            print(f"DEBUG: Extracted timestamp: {timestamp_str}")
                            try:
                                timestamp = int(timestamp_str)
                                # Try to handle both seconds and milliseconds timestamps
                                if timestamp > 253402300799:  # Year 9999 in seconds
                                    timestamp = timestamp / 1000  # Convert from milliseconds to seconds
                                file_date = datetime.fromtimestamp(timestamp).date()
                                print(f"DEBUG: File date: {file_date}, Selected date: {selected_date}")
                            except (ValueError, OverflowError) as e:
                                print(f"DEBUG: Error parsing timestamp {timestamp_str}: {e}")
                                # Fallback to file modification time
                                mtime = os.path.getmtime(file_path)
                                file_date = datetime.fromtimestamp(mtime).date()
                                print(f"DEBUG: Using mtime date fallback: {file_date}")
                            
                            # Only include if date matches the selected date
                            if file_date == selected_date:
                                print(f"DEBUG: Date match! Adding recording {file}")
                                recordings.append(get_recording_info(file, file_path, camera_name, recordings_dir))
                                matching_date_count += 1
                            else:
                                print(f"DEBUG: Date mismatch. File date: {file_date}, Selected date: {selected_date}")
                    else:
                        # If we can't determine date from filename, use modification time
                        mtime = os.path.getmtime(file_path)
                        file_date = datetime.fromtimestamp(mtime).date()
                        print(f"DEBUG: Using mtime date: {file_date}")
                        if file_date == selected_date:
                            print(f"DEBUG: Date match (mtime)! Adding recording {file}")
                            recordings.append(get_recording_info(file, file_path, camera_name, recordings_dir))
                            matching_date_count += 1
                except (ValueError, IndexError) as e:
                    # If we couldn't parse the date, log it and continue
                    print(f"Error parsing date for {file}: {e}")
                    continue
                    
        print(f"DEBUG: Found {file_count} total files, {flv_count} FLV files, {matching_camera_count} matching camera, {matching_date_count} matching date")
        print(f"DEBUG: Final recordings count: {len(recordings)}")
    except Exception as e:
        print(f"Error scanning recordings directory: {e}")
        # Continue with any recordings we've found so far
    
    # If no recordings found via timestamp matching, try a more lenient approach with file mtime
    if not recordings and flv_count > 0:
        print(f"DEBUG: No recordings matched by date, trying to match ANY FLV file by camera name")
        for file in os.listdir(recordings_dir):
            if file.endswith('.flv') and (not camera_name or file.startswith(camera_name)):
                file_path = os.path.join(recordings_dir, file)
                if os.path.isfile(file_path):
                    print(f"DEBUG: Adding any matching recording (fallback): {file}")
                    recordings.append(get_recording_info(file, file_path, camera_name, recordings_dir))
    
    # Sort recordings by timestamp
    return sorted(recordings, key=lambda x: x['timestamp'])

def get_recording_info(filename, file_path, camera_name, recordings_dir=None):
    """Extract information about a recording file"""
    if recordings_dir is None:
        recordings_dir = os.getenv('RECORDINGS_PATH', '/mnt/data')
        # Handle relative paths
        if not os.path.isabs(recordings_dir):
            recordings_dir = os.path.join(os.getcwd(), recordings_dir)
        
    try:
        # Get file stats
        stat = os.stat(file_path)
        
        # Try to extract timestamp from filename
        timestamp = None
        if '-' in filename:
            parts = filename.split('-', 1)
            if len(parts) == 2:
                timestamp_str = parts[1].replace('.flv', '')
                try:
                    timestamp = int(timestamp_str)
                    # Try to handle both seconds and milliseconds timestamps
                    if timestamp > 253402300799:  # Year 9999 in seconds
                        timestamp = timestamp / 1000  # Convert from milliseconds to seconds
                except (ValueError, OverflowError):
                    timestamp = int(stat.st_mtime)
        
        if timestamp is None:
            timestamp = int(stat.st_mtime)
        
        # Get file size
        size_bytes = stat.st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        
        # Calculate relative path for URL
        rel_path = os.path.relpath(file_path, recordings_dir)
        
        return {
            'filename': filename,
            'camera': camera_name,
            'timestamp': timestamp,
            'datetime': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'time': datetime.fromtimestamp(timestamp).strftime('%H:%M:%S'),
            'size': size_bytes,
            'size_str': size_str,
            'path': rel_path,
            'url': f"/recording/{rel_path}"
        }
    except Exception as e:
        # Return a basic info object if we can't extract details
        try:
            # Try to get relative path even if other processing failed
            rel_path = os.path.relpath(file_path, recordings_dir)
        except:
            # If all else fails, just use the filename
            rel_path = filename
            
        return {
            'filename': filename,
            'camera': camera_name,
            'timestamp': 0,
            'datetime': 'Unknown',
            'time': 'Unknown',
            'size': 0,
            'size_str': 'Unknown',
            'path': rel_path,
            'url': f"/recording/{rel_path}",
            'error': str(e)
        }

def generate_thumbnail(video_path, time_offset='00:00:05'):
    """Generate a thumbnail from a video file"""
    try:
        # Use ffmpeg to extract a frame from the video
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', time_offset,  # Seek to 5 seconds
            '-vframes', '1',     # Extract one frame
            '-vf', 'scale=320:-1',  # Scale to 320px width
            '-f', 'image2pipe',  # Output to pipe
            '-c:v', 'png',       # Output format
            '-'                  # Output to stdout
        ]
        
        result = subprocess.run(cmd, capture_output=True, check=True)
        
        # Convert the binary image data to base64
        image_b64 = base64.b64encode(result.stdout).decode('utf-8')
        
        # Return data URL
        return f"data:image/png;base64,{image_b64}"
    except subprocess.CalledProcessError as e:
        # If error, try another method (extract first frame)
        try:
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vframes', '1',
                '-vf', 'scale=320:-1',
                '-f', 'image2pipe',
                '-c:v', 'png',
                '-'
            ]
            result = subprocess.run(cmd, capture_output=True, check=True)
            image_b64 = base64.b64encode(result.stdout).decode('utf-8')
            return f"data:image/png;base64,{image_b64}"
        except:
            raise Exception(f"Failed to generate thumbnail: {e.stderr.decode('utf-8')}")

def generate_calendar_data(selected_date, available_dates):
    """Generate calendar data for a month containing the selected date"""
    year = selected_date.year
    month = selected_date.month
    
    # Convert available_dates to set for faster lookup
    available_dates_set = set(available_dates)
    
    # Get first day of month and number of days in month
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    num_days = last_day.day
    
    # Calculate first day of week (0 = Monday, 6 = Sunday)
    first_weekday = first_day.weekday()
    
    # Generate calendar weeks
    calendar_data = []
    day = 1
    for week in range(6):  # Max 6 weeks in a month
        week_data = []
        for weekday in range(7):  # 7 days per week
            if (week == 0 and weekday < first_weekday) or day > num_days:
                # Empty cell
                week_data.append({
                    'day': None,
                    'date': None,
                    'has_recordings': False,
                    'is_today': False,
                    'is_selected': False
                })
            else:
                # Date cell
                current_date = date(year, month, day)
                is_today = current_date == date.today()
                is_selected = current_date == selected_date
                has_recordings = current_date in available_dates_set
                
                week_data.append({
                    'day': day,
                    'date': current_date.strftime('%Y-%m-%d'),
                    'has_recordings': has_recordings,
                    'is_today': is_today,
                    'is_selected': is_selected
                })
                day += 1
        
        calendar_data.append(week_data)
        if day > num_days:
            break
    
    return {
        'year': year,
        'month': month,
        'month_name': first_day.strftime('%B'),
        'weeks': calendar_data,
        'prev_month': (first_day - timedelta(days=1)).strftime('%Y-%m'),
        'next_month': (last_day + timedelta(days=1)).strftime('%Y-%m')
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', 5001)), debug=False)