from sqlmodel import SQLModel, create_engine, Session
from ..utils.config import settings
import os

# Import all models to register them with SQLModel
from .models.core import Tenant, User, Fleet, Job  # noqa: F401
from .models.identity_models import (  # noqa: F401
    IdentityEndpoint, IdentityCertificate, IdentityPolicy,
    IdentityRenewalJob, IdentityAuditLog, IdentityAgent
)
from .models.enablement_models import * # noqa: F401

# Default to local sqlite for ease of deployment in MVP
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tg_platform.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
