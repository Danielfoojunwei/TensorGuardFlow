from sqlmodel import SQLModel, create_engine, Session
from ..utils.config import settings
import os

# Default to local sqlite for ease of deployment in MVP
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tg_platform.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
