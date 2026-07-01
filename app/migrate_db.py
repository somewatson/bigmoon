import os
from app.models import db
from app.main import create_app

def migrate():
    app = create_app()
    with app.app_context():
        try:
            # SQLite doesn't support adding columns via SQLAlchemy's create_all() 
            # if the table already exists. We must use raw SQL.
            db.session.execute(db.text("ALTER TABLE download_task ADD COLUMN url TEXT"))
            db.session.commit()
            print("Successfully added 'url' column to download_task table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("Column 'url' already exists. Skipping migration.")
            else:
                print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
