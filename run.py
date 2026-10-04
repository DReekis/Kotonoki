from app import create_app
from app.extensions import db

app = create_app()

def init_db():
    with app.app_context():
        db.create_all()
        print("Kotonoki database initialized successfully.")

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
