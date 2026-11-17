
from alembic import op
import sqlalchemy as sa


revision = "7a21c4d9e610"
down_revision = "46b4e0281a7a"
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "access_credentials",

        sa.Column(
            "id",
            sa.String(length=36),
            primary_key=True
        ),

        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey(
                "customers.id",
                ondelete="RESTRICT"
            ),
            nullable=False
        ),

        sa.Column(
            "entity_type",
            sa.String(length=20),
            nullable=False
        ),

        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ),

        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True
        ),

        sa.CheckConstraint(
            "entity_type IN ('booking', 'membership')",
            name="ck_access_credential_entity_type"
        ),

        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            name="uq_access_credential_entity"
        )
    )

    op.create_index(
        "ix_access_credentials_customer_id",
        "access_credentials",
        ["customer_id"]
    )

    op.create_index(
        "ix_access_credentials_customer_entity",
        "access_credentials",
        ["customer_id", "entity_type"]
    )


def downgrade():

    op.drop_index(
        "ix_access_credentials_customer_entity",
        table_name="access_credentials"
    )

    op.drop_index(
        "ix_access_credentials_customer_id",
        table_name="access_credentials"
    )

    op.drop_table("access_credentials")
