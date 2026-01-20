"""Add Organization Membership and RBAC

Enterprise multi-tenancy with role-based access control:
- OrganizationMembership table for user-to-org relationships
- OrganizationRole enum: OWNER > ADMIN > OPERATOR > READONLY
- settings_json column on Tenant for org-wide policies

Revision ID: 004_organization_membership
Revises: 003_fedmoe_experts
Create Date: 2026-01-19
"""
from alembic import op
import sqlalchemy as sa

revision = "004_organization_membership"
down_revision = "003_fedmoe_experts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add settings_json to tenant table for org-wide configuration
    op.add_column(
        "tenant",
        sa.Column("settings_json", sa.String(), nullable=False, server_default="{}")
    )

    # Create organization_membership table
    op.create_table(
        "organization_membership",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="readonly"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("invited_by_user_id", sa.String(), nullable=True),
        sa.Column("is_accepted", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_membership_user_id",
        "organization_membership",
        ["user_id"]
    )
    op.create_index(
        "ix_membership_org_id",
        "organization_membership",
        ["organization_id"]
    )
    op.create_index(
        "ix_membership_org_role",
        "organization_membership",
        ["organization_id", "role"]
    )
    op.create_index(
        "ix_membership_user_accepted",
        "organization_membership",
        ["user_id", "is_accepted"]
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_membership_user_accepted", table_name="organization_membership")
    op.drop_index("ix_membership_org_role", table_name="organization_membership")
    op.drop_index("ix_membership_org_id", table_name="organization_membership")
    op.drop_index("ix_membership_user_id", table_name="organization_membership")

    # Drop table
    op.drop_table("organization_membership")

    # Remove settings_json from tenant
    op.drop_column("tenant", "settings_json")
