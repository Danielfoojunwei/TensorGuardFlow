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
from .models.evidence_models import * # noqa: F401
from .models.peft_models import ( # noqa: F401
    IntegrationConfig, PeftWizardDraft, PeftRun
)
from .models.fedmoe_models import FedMoEExpert, SkillEvidence # noqa: F401
from .models.settings_models import SystemSetting # noqa: F401

# Default to local sqlite for ease of deployment in MVP
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for dev, but warn loudly
    import logging
    logging.getLogger(__name__).warning("DATABASE_URL not set, using local SQLite (NOT FOR PRODUCTION)")
    DATABASE_URL = "sqlite:///./tg_platform.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
