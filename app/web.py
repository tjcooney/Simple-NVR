from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import requests
from dotenv import load_dotenv
import os
import logging
from datetime import timedelta
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

@app.route('/')
@login_required
def index():
    session = init_db()
    cameras = session.query(Camera).all()
    return render_template('index.html', 
                         title=app.config['WEBSITE_TITLE'], 
                         cameras=cameras)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', 5001)), debug=False)