"""Create sessions, messages, and feedback tables.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("owner_subject", sa.String(255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("archived_at", sa.String(32)),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_sessions_owner_status_created",
        "sessions",
        ["owner_subject", "status", "created_at"],
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(255),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "session_id", "sequence", name="uq_messages_session_sequence"
        ),
        sa.UniqueConstraint("id", "session_id", name="uq_messages_id_session"),
    )
    op.create_index(
        "ix_messages_session_sequence", "messages", ["session_id", "sequence"]
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(255),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("owner_subject", sa.String(255), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id", "session_id"],
            ["messages.id", "messages.session_id"],
            ondelete="CASCADE",
            name="fk_feedback_message_session",
        ),
        sa.UniqueConstraint("message_id", name="uq_feedback_message"),
    )
    op.create_index(
        "ix_feedback_session_created", "feedback", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("messages")
    op.drop_table("sessions")
