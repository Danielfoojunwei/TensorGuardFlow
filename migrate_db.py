
from sqlmodel import Session, text
from tensorguard.platform.database import engine

def migrate():
    with Session(engine) as session:
        try:
            # Check if column exists
            session.exec(text("SELECT version FROM fedmoeexpert LIMIT 1"))
            print("Column 'version' already exists.")
        except Exception:
            print("Adding 'version' column to fedmoeexpert...")
            session.exec(text("ALTER TABLE fedmoeexpert ADD COLUMN version VARCHAR DEFAULT 'v1.0'"))
            session.commit()
            print("Migration successful.")

if __name__ == "__main__":
    migrate()
