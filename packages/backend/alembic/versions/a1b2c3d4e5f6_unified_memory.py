"""unified memory schema

Revision ID: a1b2c3d4e5f6
Revises: c8d368babd46
Create Date: 2026-10-01 17:45:00.000000

Adds the `memories` table for cross-LLM unified memory. The legacy
`memories` table (id, key, value, kind, score, created_at, updated_at) is
NOT migrated: the new schema is the single source of truth for the
UNIFIED MEMORY feature.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c8d368babd46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Idempotent on purpose: `v6/axum-poc/src/state.rs::init_db` also creates this
    table with `CREATE TABLE IF NOT EXISTS` on every Axum boot, so an unguarded
    create would abort `alembic upgrade head` with "table memories already
    exists" and wedge every later migration.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("memories"):
        op.create_table('memories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', sa.Text(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('source_llm', sa.String(length=64), nullable=True),
    sa.Column('source_agent', sa.String(length=128), nullable=True),
    sa.Column('expiry_at', sa.Float(), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_memories_id'), 'memories', ['id'], unique=False)
        op.create_index(op.f('ix_memories_type'), 'memories', ['type'], unique=False)
        op.create_index(op.f('ix_memories_source_llm'), 'memories', ['source_llm'], unique=False)
        op.create_index(op.f('ix_memories_source_agent'), 'memories', ['source_agent'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema.

    Restores the legacy shape: dropping `memories` without renaming
    `memories_legacy` back left the database in a state no code path produces,
    and the legacy rows were only reachable under a name nothing reads.
    """
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("memories"):
        return
    op.drop_index(op.f('ix_memories_source_agent'), table_name='memories')
    op.drop_index(op.f('ix_memories_source_llm'), table_name='memories')
    op.drop_index(op.f('ix_memories_type'), table_name='memories')
    op.drop_index(op.f('ix_memories_id'), table_name='memories')
    op.drop_table('memories')
    if inspector.has_table("memories_legacy"):
        op.rename_table("memories_legacy", "memories")
    # ### end Alembic commands ###