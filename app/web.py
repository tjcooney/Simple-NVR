from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import requests
from dotenv import load_dotenv
import os
import logging
from .database import init_db, Camera

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-default-secret-key')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.config['WEBSITE_TITLE'] = os.getenv('WEBSITE_TITLE', 'Default Title')

@app.route('/')
def index():
    session = init_db()
    cameras = session.query(Camera).all()
    return render_template('index.html', title=app.config['WEBSITE_TITLE'], cameras=cameras)


@app.route('/add_camera', methods=['GET', 'POST'])
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
def view_camera(camera_id):
    session = init_db()
    camera = session.query(Camera).filter_by(id=camera_id).first()
    if not camera:
        flash('Camera not found.', 'error')
        return redirect(url_for('index'))
    return render_template('view_camera.html', camera=camera)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', 5001)), debug=False)
