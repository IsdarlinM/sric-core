"""initial schema"""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("records", sa.Column("id", sa.String(64), primary_key=True), sa.Column("kind", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_records_kind", "records", ["kind"])
    op.create_index("ix_records_status", "records", ["status"])
    op.create_table("edges", sa.Column("id", sa.String(64), primary_key=True), sa.Column("source_id", sa.String(64), nullable=False), sa.Column("target_id", sa.String(64), nullable=False), sa.Column("relationship_type", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False))
    op.create_index("ix_edges_source_id", "edges", ["source_id"])
    op.create_index("ix_edges_target_id", "edges", ["target_id"])
    op.create_index("ix_edges_relationship_type", "edges", ["relationship_type"])
    op.create_table("schema_meta", sa.Column("key", sa.String(64), primary_key=True), sa.Column("value", sa.Text(), nullable=False))

def downgrade() -> None:
    op.drop_table("schema_meta")
    op.drop_table("edges")
    op.drop_table("records")
