"""
Database setup script for Groupdoo
This script helps initialize the database tables
"""
from app import app, db

def init_database():
    """Initialize the database tables"""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✓ Database tables created successfully!")
        print(f"✓ Database URI: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1]}")
        print("\nYou can now run the application with: python app.py")

if __name__ == '__main__':
    print("Initializing database...")
    init_database()

