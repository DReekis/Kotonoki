import os
import sys
from pathlib import Path

# Ensure root directory is on sys.path for serverless execution
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app import create_app
from app.extensions import db
from seed import seed_initial_data

# Create Flask WSGI application instance
app = create_app()

# Auto-initialize database tables and seed dispatches on cold start
with app.app_context():
    try:
        db.create_all()
        seed_initial_data()
    except Exception as e:
        print(f"Database initialization note: {e}")
