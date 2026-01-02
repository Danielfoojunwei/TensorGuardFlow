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

def seed_db():
    """Seed the database with mock data for the Enterprise PLM demo."""
    from .models.core import Tenant, User, UserRole
    from .models.evidence_models import Run
    from .models.identity_models import IdentityEndpoint, IdentityCertificate, IdentityPolicy, IdentityAuditLog, EndpointType, Criticality, AuditAction
    from datetime import datetime, timedelta
    
    with Session(engine) as session:
        # 1. Check if seeded
        if session.exec(select(User).where(User.email == "admin@tensorguard.ai")).first():
            return
            
        # 2. Add Tenant & User
        tenant = Tenant(id="T-DEMO-99", name="Siemens Mobility")
        session.add(tenant)
        user = User(
            id="U-FOO",
            tenant_id="T-DEMO-99",
            email="admin@tensorguard.ai",
            hashed_password="...", # Not used in demo bypass
            role=UserRole.ORG_ADMIN
        )
        session.add(user)
        
        # 3. Add Model Runs (Lineage)
        run1 = Run(
            run_id="R-7721-BC",
            schema_version="2.0",
            sdk_version="2.1.4-v2",
            git_commit="a7f23c1",
            status="completed",
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
        run2 = Run(
            run_id="R-7722-AF",
            schema_version="2.0",
            sdk_version="2.1.4-v2",
            git_commit="b8e110d",
            status="evaluated",
            created_at=datetime.utcnow() - timedelta(minutes=45)
        )
        session.add_all([run1, run2])

        # 4. Add Identity Endpoints
        ep1 = IdentityEndpoint(
            id="E-EDGE-01",
            tenant_id="T-DEMO-99",
            fleet_id="F-LHR-01",
            name="London Edge Node 01",
            hostname="edge-01.lhr.siemens.com",
            endpoint_type=EndpointType.KUBERNETES,
            criticality=Criticality.HIGH
        )
        ep2 = IdentityEndpoint(
            id="E-EDGE-02",
            tenant_id="T-DEMO-99",
            fleet_id="F-LHR-01",
            name="London Edge Node 02",
            hostname="edge-02.lhr.siemens.com",
            endpoint_type=EndpointType.KUBERNETES,
            criticality=Criticality.HIGH
        )
        session.add_all([ep1, ep2])
        
        # 5. Add Identity Inventory (Key Vault)
        cert1 = IdentityCertificate(
            id="C-901",
            tenant_id="T-DEMO-99",
            endpoint_id="E-EDGE-01",
            subject_dn="CN=edge-agent-01.tensorguard.ai",
            issuer_dn="CN=TensorGuard Fleet CA",
            serial_number="901001",
            sans_json='["edge-agent-01.tensorguard.ai"]',
            signature_algorithm="SHA256WithRSA",
            not_before=datetime.utcnow() - timedelta(days=30),
            not_after=datetime.utcnow() + timedelta(days=60),
            fingerprint_sha256="4af6..."
        )
        cert2 = IdentityCertificate(
            id="C-902",
            tenant_id="T-DEMO-99",
            endpoint_id="E-EDGE-02",
            subject_dn="CN=edge-agent-02.tensorguard.ai",
            issuer_dn="CN=TensorGuard Fleet CA",
            serial_number="902002",
            sans_json='["edge-agent-02.tensorguard.ai"]',
            signature_algorithm="SHA256WithRSA",
            not_before=datetime.utcnow() - timedelta(days=80),
            not_after=datetime.utcnow() + timedelta(days=10),
            fingerprint_sha256="5bc7..."
        )
        session.add_all([cert1, cert2])

        # 6. Add Audit Logs
        log1 = IdentityAuditLog(
            sequence_number=1,
            tenant_id="T-DEMO-99",
            actor_type="system",
            actor_id="system-init",
            action=AuditAction.AGENT_ENROLLED,
            target_type="agent",
            target_id="A-LHR-01",
            payload_hash="e3b0...", # empty
            prev_hash="GENESIS",
            entry_hash="..."
        )
        log1.entry_hash = IdentityAuditLog.compute_entry_hash(log1.prev_hash, log1.action.value, log1.payload_hash, log1.timestamp)
        
        log2 = IdentityAuditLog(
            sequence_number=2,
            tenant_id="T-DEMO-99",
            actor_type="user",
            actor_id="U-FOO",
            action=AuditAction.CERT_DISCOVERED,
            target_type="certificate",
            target_id="C-901",
            payload_hash="e3b0...", 
            prev_hash=log1.entry_hash,
            entry_hash="..."
        )
        log2.entry_hash = IdentityAuditLog.compute_entry_hash(log2.prev_hash, log2.action.value, log2.payload_hash, log2.timestamp)
        
        session.add_all([log1, log2])
        
        session.commit()

def get_session():
    with Session(engine) as session:
        yield session
