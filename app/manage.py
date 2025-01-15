# app/manage.py
from .database import init_db, Camera

def add_camera(name, stream_url, username=None, password=None):
    session = init_db()
    
    # Create new camera
    camera = Camera(
        name=name,
        stream_url=stream_url,
        username=username,
        password=password
    )
    
    # Add to database
    session.add(camera)
    session.commit()
    print(f"Added camera: {name}")

def list_cameras():
    session = init_db()
    cameras = session.query(Camera).all()
    
    if not cameras:
        print("No cameras found in database")
        return
        
    print("\nRegistered Cameras:")
    print("-" * 50)
    for camera in cameras:
        print(f"Name: {camera.name}")
        print(f"Stream URL: {camera.stream_url}")
        if camera.username:
            print(f"Username: {camera.username}")
        print("-" * 50)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Add camera: python manage.py add <name> <stream_url> [username] [password]")
        print("  List cameras: python manage.py list")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        list_cameras()
    elif command == "add":
        if len(sys.argv) < 4:
            print("Error: Name and stream URL required")
            sys.exit(1)
        name = sys.argv[2]
        stream_url = sys.argv[3]
        username = sys.argv[4] if len(sys.argv) > 4 else None
        password = sys.argv[5] if len(sys.argv) > 5 else None
        add_camera(name, stream_url, username, password)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)