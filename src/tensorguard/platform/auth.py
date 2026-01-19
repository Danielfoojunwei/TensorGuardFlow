"""
TensorGuard Platform Authentication Module

Provides JWT-based authentication with enterprise security defaults:
- Argon2id password hashing (memory-hard, GPU-resistant)
- Configurable token expiration with secure defaults
- Role-based access control (RBAC)
- Password strength validation
- Rate limiting support via Redis (optional)
- Token issuer/audience validation
"""

import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from .database import get_session
from .models.core import User, UserRole

logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# JWT Configuration - MUST be set in production
from ..utils.production_gates import is_production, ProductionGateError, require_env

SECRET_KEY = os.getenv("TG_SECRET_KEY")
if not SECRET_KEY:
    if is_production():
        require_env(
            "TG_SECRET_KEY",
            remediation="Set TG_SECRET_KEY environment variable: export TG_SECRET_KEY=$(python -c \"import secrets; print(secrets.token_hex(32))\")",
            min_length=32,
        )
    else:
        logger.warning(
            "SECURITY WARNING: TG_SECRET_KEY not set. "
            "Generating ephemeral key - tokens will be invalid after restart. "
            "Set TG_SECRET_KEY environment variable for production."
        )
        SECRET_KEY = secrets.token_hex(32)

# Use HS256 for simplicity, but ensure key is at least 256 bits
ALGORITHM = os.getenv("TG_JWT_ALGORITHM", "HS256")

# Token expiration - short-lived for security
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TG_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("TG_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Token validation
TOKEN_ISSUER = os.getenv("TG_TOKEN_ISSUER", "tensorguard-platform")
TOKEN_AUDIENCE = os.getenv("TG_TOKEN_AUDIENCE", "tensorguard-api")

# Password policy
MIN_PASSWORD_LENGTH = int(os.getenv("TG_MIN_PASSWORD_LENGTH", "12"))
REQUIRE_PASSWORD_COMPLEXITY = os.getenv("TG_REQUIRE_PASSWORD_COMPLEXITY", "true").lower() == "true"

# Rate limiting (requires Redis)
ENABLE_RATE_LIMITING = os.getenv("TG_ENABLE_RATE_LIMITING", "false").lower() == "true"
MAX_LOGIN_ATTEMPTS = int(os.getenv("TG_MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("TG_LOCKOUT_DURATION_MINUTES", "15"))

# ============================================================================
# PASSWORD HASHING
# ============================================================================

# Argon2id with OWASP-recommended parameters
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64 MiB
    argon2__time_cost=3,        # 3 iterations
    argon2__parallelism=4,      # 4 threads
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


class PasswordValidationError(ValueError):
    """Raised when password doesn't meet security requirements."""
    pass


def validate_password_strength(password: str) -> None:
    """
    Validate password meets security requirements.

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )

    if REQUIRE_PASSWORD_COMPLEXITY:
        checks = [
            (r'[a-z]', "lowercase letter"),
            (r'[A-Z]', "uppercase letter"),
            (r'\d', "digit"),
            (r'[!@#$%^&*(),.?":{}|<>]', "special character"),
        ]
        missing = []
        for pattern, name in checks:
            if not re.search(pattern, password):
                missing.append(name)

        if missing:
            raise PasswordValidationError(
                f"Password must contain: {', '.join(missing)}"
            )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str, validate: bool = True) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password
        validate: If True, validate password strength before hashing

    Returns:
        Hashed password

    Raises:
        PasswordValidationError: If validation enabled and password is weak
    """
    if validate:
        validate_password_strength(password)
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access"
) -> str:
    """
    Create a JWT access token with security claims.

    Args:
        data: Token payload data
        expires_delta: Optional custom expiration
        token_type: Token type (access or refresh)

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    # Use timezone-aware datetime (Python 3.11+ compatible)
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": now,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "type": token_type,
        "jti": secrets.token_hex(16),  # Unique token ID for revocation
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token."""
    return create_access_token(
        data,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh"
    )

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> User:
    """
    Validate JWT token and return the authenticated user.

    Validates:
    - Token signature and expiration
    - Token issuer and audience
    - Token type (must be 'access')
    - User existence in database

    Raises:
        HTTPException: 401 if authentication fails
    """
    # --- DEMO MODE BYPASS ---
    # SECURITY: Demo mode is OFF by default. Set TG_DEMO_MODE=true ONLY in dev/test.
    # In production, this should NEVER be enabled.
    DEMO_MODE = os.getenv("TG_DEMO_MODE", "false").lower() == "true"
    if DEMO_MODE:
        if os.getenv("TG_ENVIRONMENT", "development") == "production":
            logger.critical("SECURITY VIOLATION: TG_DEMO_MODE=true in production environment!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Demo mode is not allowed in production"
            )
        if not token:
            logger.warning("DEMO MODE: Returning demo user (no token required) - NOT FOR PRODUCTION")
            demo_user = User(
                id="demo-user-001",
                email="demo@tensorguard.local",
                name="Demo User",
                role=UserRole.ORG_ADMIN,
                tenant_id="fceac734-e672-4a0c-863b-c7bb8e28b88e",
                hashed_password="N/A"
            )
            return demo_user
    # --- END DEMO MODE ---
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
        )

        # Validate token type
        token_type = payload.get("type")
        if token_type != "access":
            logger.warning(f"Invalid token type: {token_type}")
            raise credentials_exception

        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception

    except JWTError as e:
        logger.debug(f"JWT validation failed: {e}")
        raise credentials_exception

    user = session.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    # Check if user is active (if such field exists)
    if hasattr(user, 'is_active') and not user.is_active:
        logger.warning(f"Inactive user attempted access: {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    return user

class RoleChecker:
    """
    RBAC dependency for FastAPI routes.

    Usage:
        @app.get("/admin", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
        async def admin_endpoint():
            ...
    """

    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role not in self.allowed_roles:
            logger.warning(
                f"RBAC denied: user={user.email} role={user.role} "
                f"required={[r.value for r in self.allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for your role"
            )
        return user


# ============================================================================
# API KEY ENCRYPTION (for HMAC verification)
# ============================================================================

def _get_fernet_key() -> bytes:
    """
    Derive a Fernet-compatible key from TG_SECRET_KEY.
    Fernet requires a 32-byte URL-safe base64-encoded key.
    """
    import hashlib
    import base64
    # Use SHA256 to derive a 32-byte key from SECRET_KEY
    derived = hashlib.sha256(SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_api_key(raw_key: str) -> str:
    """
    Encrypt an API key for secure storage.

    Args:
        raw_key: The raw API key to encrypt

    Returns:
        Fernet-encrypted key as a string
    """
    from cryptography.fernet import Fernet
    fernet = Fernet(_get_fernet_key())
    encrypted = fernet.encrypt(raw_key.encode())
    return encrypted.decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an encrypted API key.

    Args:
        encrypted_key: The Fernet-encrypted key

    Returns:
        The raw API key

    Raises:
        InvalidToken: If decryption fails (wrong key or corrupted data)
    """
    from cryptography.fernet import Fernet
    fernet = Fernet(_get_fernet_key())
    decrypted = fernet.decrypt(encrypted_key.encode())
    return decrypted.decode()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def require_roles(*roles: UserRole):
    """
    Decorator-style dependency for role checking.

    Usage:
        @app.get("/admin")
        async def admin_endpoint(user: User = Depends(require_roles(UserRole.ADMIN))):
            ...
    """
    return RoleChecker(list(roles))


# Pre-configured role checkers for common use cases
require_org_admin = RoleChecker([UserRole.ORG_ADMIN])
require_site_admin = RoleChecker([UserRole.ORG_ADMIN, UserRole.SITE_ADMIN])
require_operator = RoleChecker([UserRole.ORG_ADMIN, UserRole.SITE_ADMIN, UserRole.OPERATOR])


def get_token_info(token: str) -> Optional[Dict]:
    """
    Decode a token without full validation (for debugging/logging).

    WARNING: This does NOT validate the token. Use only for logging/debugging.
    """
    try:
        # Decode without verification for inspection
        return jwt.decode(token, options={"verify_signature": False})
    except JWTError:
        return None


# ============================================================================
# FLEET BEARER AUTHENTICATION
# ============================================================================

from fastapi import Header
from sqlmodel import select
import hashlib

def verify_fleet_api_key(raw_key: str, stored_hash: str) -> bool:
    """
    Verify a Fleet API key by comparing SHA256 hashes.

    Args:
        raw_key: The raw API key sent by the client
        stored_hash: The SHA256 hash stored in the database

    Returns:
        True if the key is valid, False otherwise
    """
    computed_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return secrets.compare_digest(computed_hash, stored_hash)


async def get_current_fleet(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: Session = Depends(get_session)
):
    """
    Validate Fleet Bearer token and return the authenticated Fleet.

    Expected header format: Authorization: Fleet <raw_api_key>

    Authentication flow:
    1. Extract raw_api_key from Authorization header
    2. Hash the raw key with SHA256
    3. Compare hash with stored api_key_hash in Fleet table
    4. Verify fleet is active

    Args:
        authorization: Authorization header value
        session: Database session

    Returns:
        Fleet object if authentication succeeds

    Raises:
        HTTPException: 401 if authentication fails
    """
    from .models.core import Fleet

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Fleet API key",
        headers={"WWW-Authenticate": "Fleet"},
    )

    if not authorization:
        logger.debug("Fleet auth: No Authorization header")
        raise credentials_exception

    # Parse "Fleet <api_key>" format
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "fleet":
        logger.debug(f"Fleet auth: Invalid Authorization format: {parts[0] if parts else 'empty'}")
        raise credentials_exception

    raw_key = parts[1]

    # Find fleet by hashing the raw key and comparing
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    stmt = select(Fleet).where(Fleet.api_key_hash == key_hash)
    fleet = session.exec(stmt).first()

    if not fleet:
        logger.warning("Fleet auth: No fleet found with matching API key hash")
        raise credentials_exception

    if not fleet.is_active:
        logger.warning(f"Fleet auth: Fleet {fleet.id} is inactive")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fleet is inactive"
        )

    logger.debug(f"Fleet auth: Successfully authenticated fleet {fleet.id}")
    return fleet


async def get_current_fleet_optional(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: Session = Depends(get_session)
):
    """
    Optionally validate Fleet Bearer token.

    Returns None if no auth provided (for endpoints that support both auth modes).
    """
    if not authorization:
        return None

    if not authorization.lower().startswith("fleet "):
        return None

    try:
        return await get_current_fleet(authorization, session)
    except HTTPException:
        return None


# ============================================================================
# ORGANIZATION RBAC (Multi-tenant Role-Based Access Control)
# ============================================================================

from dataclasses import dataclass
from .models.core import OrganizationRole, OrganizationMembership, Tenant


@dataclass
class OrgAuthContext:
    """
    Authentication context for organization-scoped operations.

    Provides:
    - user: The authenticated user
    - organization: The target organization (tenant)
    - membership: The user's membership in this org
    - role: The user's role in this org (convenience accessor)

    Usage in endpoints:
        async def my_endpoint(auth: OrgAuthContext = Depends(require_org_role(OrganizationRole.ADMIN))):
            print(f"User {auth.user.email} has role {auth.role} in org {auth.organization.name}")
    """
    user: User
    organization: Tenant
    membership: OrganizationMembership
    role: OrganizationRole


def get_user_org_membership(
    user_id: str,
    org_id: str,
    session: Session
) -> Optional[OrganizationMembership]:
    """
    Get a user's membership in a specific organization.

    Args:
        user_id: The user's ID
        org_id: The organization's ID
        session: Database session

    Returns:
        OrganizationMembership if found and accepted, None otherwise
    """
    stmt = select(OrganizationMembership).where(
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.is_accepted == True
    )
    return session.exec(stmt).first()


def get_user_org_role(
    user_id: str,
    org_id: str,
    session: Session
) -> Optional[OrganizationRole]:
    """
    Get a user's role in a specific organization.

    Args:
        user_id: The user's ID
        org_id: The organization's ID
        session: Database session

    Returns:
        OrganizationRole if user is a member, None otherwise
    """
    membership = get_user_org_membership(user_id, org_id, session)
    if membership:
        return membership.role
    return None


class OrgRoleChecker:
    """
    RBAC dependency for organization-scoped operations.

    Validates:
    1. User is authenticated (JWT valid)
    2. User has membership in the target organization
    3. User's role meets minimum required level

    The organization is determined by:
    - org_id path/query parameter, or
    - User's primary tenant_id (fallback for backward compatibility)

    Usage:
        @app.get("/org/{org_id}/fleets")
        async def list_fleets(
            org_id: str,
            auth: OrgAuthContext = Depends(require_org_role(OrganizationRole.READONLY))
        ):
            # auth.organization.id == org_id
            # auth.role >= OrganizationRole.READONLY
            ...
    """

    def __init__(self, min_role: OrganizationRole):
        self.min_role = min_role

    async def __call__(
        self,
        request: Request,
        org_id: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session)
    ) -> OrgAuthContext:
        # Determine target organization
        # Priority: path param > query param > user's primary tenant
        target_org_id = org_id
        if not target_org_id:
            # Try to get from path params
            target_org_id = request.path_params.get("org_id")
        if not target_org_id:
            # Fallback to user's primary tenant (backward compat)
            target_org_id = current_user.tenant_id

        # Fetch the organization
        organization = session.get(Tenant, target_org_id)
        if not organization:
            logger.warning(f"RBAC: Organization not found: {target_org_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

        # Check user's membership
        membership = get_user_org_membership(current_user.id, target_org_id, session)

        # Fallback: if no membership exists but user's primary tenant matches,
        # check for legacy role mapping (backward compatibility)
        if not membership and current_user.tenant_id == target_org_id:
            # Create synthetic membership based on legacy role
            legacy_role_map = {
                UserRole.ORG_ADMIN: OrganizationRole.OWNER,
                UserRole.SITE_ADMIN: OrganizationRole.ADMIN,
                UserRole.OPERATOR: OrganizationRole.OPERATOR,
                UserRole.AUDITOR: OrganizationRole.READONLY,
                UserRole.SERVICE_ACCOUNT: OrganizationRole.OPERATOR,
            }
            synthetic_role = legacy_role_map.get(current_user.role, OrganizationRole.READONLY)

            # Log this for migration tracking
            logger.info(
                f"RBAC: Using legacy role mapping for user={current_user.email} "
                f"in org={target_org_id}: {current_user.role} -> {synthetic_role}"
            )

            membership = OrganizationMembership(
                id="legacy-synthetic",
                user_id=current_user.id,
                organization_id=target_org_id,
                role=synthetic_role,
                is_accepted=True
            )

        if not membership:
            logger.warning(
                f"RBAC: User {current_user.email} has no access to org {target_org_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organization"
            )

        # Check role level
        user_role = membership.role
        if not user_role.has_privilege(self.min_role):
            logger.warning(
                f"RBAC denied: user={current_user.email} role={user_role.value} "
                f"required={self.min_role.value} org={target_org_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This operation requires {self.min_role.value} role or higher"
            )

        return OrgAuthContext(
            user=current_user,
            organization=organization,
            membership=membership,
            role=user_role
        )


def require_org_role(min_role: OrganizationRole) -> OrgRoleChecker:
    """
    Factory function to create an organization role checker dependency.

    Usage:
        @app.post("/fleets")
        async def create_fleet(
            auth: OrgAuthContext = Depends(require_org_role(OrganizationRole.OPERATOR))
        ):
            # Only users with OPERATOR, ADMIN, or OWNER can create fleets
            ...

    Args:
        min_role: Minimum role required for access

    Returns:
        OrgRoleChecker dependency
    """
    return OrgRoleChecker(min_role)


# Pre-configured organization role checkers for common use cases
require_org_owner = OrgRoleChecker(OrganizationRole.OWNER)
require_org_admin = OrgRoleChecker(OrganizationRole.ADMIN)
require_org_operator = OrgRoleChecker(OrganizationRole.OPERATOR)
require_org_readonly = OrgRoleChecker(OrganizationRole.READONLY)


async def ensure_org_access(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> Tenant:
    """
    Verify user has any level of access to the specified organization.

    This is a lighter check than require_org_role - just verifies membership exists.
    Use when you need org-level scoping but don't care about specific role.

    Args:
        org_id: Organization ID to check access for
        current_user: Authenticated user
        session: Database session

    Returns:
        Tenant object if access is granted

    Raises:
        HTTPException 403 if user has no access to the org
        HTTPException 404 if org doesn't exist
    """
    organization = session.get(Tenant, org_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    membership = get_user_org_membership(current_user.id, org_id, session)

    # Backward compatibility: allow access if user's primary tenant matches
    if not membership and current_user.tenant_id == org_id:
        return organization

    if not membership:
        logger.warning(
            f"Access denied: user={current_user.email} attempted to access org={org_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization"
        )

    return organization


def ensure_fleet_access(
    fleet_id: str,
    current_user: User,
    session: Session,
    min_role: OrganizationRole = OrganizationRole.READONLY
) -> "Fleet":
    """
    Verify user has access to a fleet through organization membership.

    Args:
        fleet_id: Fleet ID to check access for
        current_user: Authenticated user
        session: Database session
        min_role: Minimum role required (default: READONLY)

    Returns:
        Fleet object if access is granted

    Raises:
        HTTPException 403 if user doesn't have required role
        HTTPException 404 if fleet doesn't exist
    """
    from .models.core import Fleet

    fleet = session.get(Fleet, fleet_id)
    if not fleet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fleet not found"
        )

    # Check user's role in the fleet's organization
    membership = get_user_org_membership(current_user.id, fleet.tenant_id, session)

    # Backward compatibility
    if not membership and current_user.tenant_id == fleet.tenant_id:
        legacy_role_map = {
            UserRole.ORG_ADMIN: OrganizationRole.OWNER,
            UserRole.SITE_ADMIN: OrganizationRole.ADMIN,
            UserRole.OPERATOR: OrganizationRole.OPERATOR,
            UserRole.AUDITOR: OrganizationRole.READONLY,
            UserRole.SERVICE_ACCOUNT: OrganizationRole.OPERATOR,
        }
        user_role = legacy_role_map.get(current_user.role, OrganizationRole.READONLY)
    elif membership:
        user_role = membership.role
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this fleet"
        )

    if not user_role.has_privilege(min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This operation requires {min_role.value} role or higher"
        )

    return fleet
