"""SQLAlchemy async SQLite persistence and Alembic lifecycle helpers."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Iterator

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from ..domain import (
    Feedback,
    FeedbackRating,
    MessageRole,
    Session,
    SessionStatus,
    StoredMessage,
)

DEFAULT_BUSY_TIMEOUT_MS = 5_000


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC timestamps as ISO text and always return aware values."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_owner_status_created", "owner_subject", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    owner_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_messages_session_sequence"),
        UniqueConstraint("id", "session_id", name="uq_messages_id_session"),
        Index("ix_messages_session_sequence", "session_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)


class FeedbackRow(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "session_id"],
            ["messages.id", "messages.session_id"],
            ondelete="CASCADE",
            name="fk_feedback_message_session",
        ),
        UniqueConstraint("message_id", name="uq_feedback_message"),
        Index("ix_feedback_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)


def sqlite_url(path: str | Path) -> str:
    """Build an async SQLite URL from a filesystem path."""
    return f"sqlite+aiosqlite:///{Path(path).expanduser().resolve().as_posix()}"


def create_sqlite_engine(
    database_url: str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> AsyncEngine:
    if not database_url.startswith("sqlite+aiosqlite:///"):
        raise ValueError("database URL must use sqlite+aiosqlite:///")
    if busy_timeout_ms < 0:
        raise ValueError("busy_timeout_ms must not be negative")
    engine = create_async_engine(database_url)

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        finally:
            cursor.close()

    return engine


def _session_from_row(row: SessionRow) -> Session:
    return Session(
        row.id,
        row.owner_subject,
        row.title,
        row.created_at,
        row.updated_at,
        SessionStatus(row.status),
        row.archived_at,
        row.metadata_,
    )


def _message_from_row(row: MessageRow) -> StoredMessage:
    return StoredMessage(
        row.id,
        row.session_id,
        row.sequence,
        MessageRole(row.role),
        row.payload,
        row.created_at,
        row.metadata_,
    )


def _feedback_from_row(row: FeedbackRow) -> Feedback:
    return Feedback(
        row.id,
        row.session_id,
        row.message_id,
        row.owner_subject,
        FeedbackRating(row.rating),
        row.created_at,
        row.updated_at,
        row.comment,
        row.metadata_,
    )


class SQLAlchemySessionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, session: Session) -> None:
        row = SessionRow(
            id=session.id,
            owner_subject=session.owner_subject,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            status=session.status.value,
            archived_at=session.archived_at,
            metadata_=session.metadata,
        )
        try:
            async with self._sessions.begin() as db:
                db.add(row)
        except IntegrityError as exc:
            raise ValueError(f"session {session.id!r} already exists") from exc

    async def get(self, session_id: str) -> Session | None:
        async with self._sessions() as db:
            row = await db.get(SessionRow, session_id)
            return None if row is None else _session_from_row(row)

    async def list_by_owner(
        self, owner_subject: str, *, include_archived: bool = False
    ) -> list[Session]:
        query = select(SessionRow).where(SessionRow.owner_subject == owner_subject)
        if not include_archived:
            query = query.where(SessionRow.status == SessionStatus.ACTIVE.value)
        query = query.order_by(SessionRow.created_at, SessionRow.id)
        async with self._sessions() as db:
            rows = (await db.scalars(query)).all()
            return [_session_from_row(row) for row in rows]

    async def update(self, session: Session) -> None:
        async with self._sessions.begin() as db:
            row = await db.get(SessionRow, session.id)
            if row is None:
                raise ValueError(f"session {session.id!r} does not exist")
            row.owner_subject = session.owner_subject
            row.title = session.title
            row.created_at = session.created_at
            row.updated_at = session.updated_at
            row.status = session.status.value
            row.archived_at = session.archived_at
            row.metadata_ = session.metadata

    async def delete(self, session_id: str) -> bool:
        async with self._sessions.begin() as db:
            row = await db.get(SessionRow, session_id)
            if row is None:
                return False
            await db.delete(row)
            return True


class SQLAlchemyTranscriptRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, message: StoredMessage) -> None:
        row = MessageRow(
            id=message.id,
            session_id=message.session_id,
            sequence=message.sequence,
            role=message.role.value,
            payload=message.payload,
            created_at=message.created_at,
            metadata_=message.metadata,
        )
        try:
            async with self._sessions.begin() as db:
                db.add(row)
        except IntegrityError as exc:
            detail = str(exc.orig).lower()
            if "sequence" in detail:
                raise ValueError(
                    f"message sequence {message.sequence} already exists in session"
                ) from exc
            if "foreign key" in detail:
                raise ValueError(
                    f"message session {message.session_id!r} does not exist"
                ) from exc
            raise ValueError(f"message {message.id!r} already exists") from exc

    async def get(self, message_id: str) -> StoredMessage | None:
        async with self._sessions() as db:
            row = await db.get(MessageRow, message_id)
            return None if row is None else _message_from_row(row)

    async def list_by_session(self, session_id: str) -> list[StoredMessage]:
        query = (
            select(MessageRow)
            .where(MessageRow.session_id == session_id)
            .order_by(MessageRow.sequence)
        )
        async with self._sessions() as db:
            rows = (await db.scalars(query)).all()
            return [_message_from_row(row) for row in rows]

    async def delete_by_session(self, session_id: str) -> None:
        async with self._sessions.begin() as db:
            rows = await db.scalars(
                select(MessageRow).where(MessageRow.session_id == session_id)
            )
            for row in rows:
                await db.delete(row)


class SQLAlchemyFeedbackRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def upsert(self, feedback: Feedback) -> Feedback:
        try:
            return await self._upsert(feedback)
        except IntegrityError as exc:
            raise ValueError("feedback violates a uniqueness or parent constraint") from exc

    async def _upsert(self, feedback: Feedback) -> Feedback:
        async with self._sessions.begin() as db:
            existing = await db.scalar(
                select(FeedbackRow).where(
                    FeedbackRow.session_id == feedback.session_id,
                    FeedbackRow.message_id == feedback.message_id,
                )
            )
            if existing is not None and existing.id != feedback.id:
                raise ValueError("feedback upsert must preserve its stable id")
            if existing is None:
                db.add(
                    FeedbackRow(
                        id=feedback.id,
                        session_id=feedback.session_id,
                        message_id=feedback.message_id,
                        owner_subject=feedback.owner_subject,
                        rating=feedback.rating.value,
                        created_at=feedback.created_at,
                        updated_at=feedback.updated_at,
                        comment=feedback.comment,
                        metadata_=feedback.metadata,
                    )
                )
            else:
                existing.owner_subject = feedback.owner_subject
                existing.rating = feedback.rating.value
                existing.created_at = feedback.created_at
                existing.updated_at = feedback.updated_at
                existing.comment = feedback.comment
                existing.metadata_ = feedback.metadata
        return feedback

    async def get_for_message(
        self, session_id: str, message_id: str
    ) -> Feedback | None:
        query = select(FeedbackRow).where(
            FeedbackRow.session_id == session_id,
            FeedbackRow.message_id == message_id,
        )
        async with self._sessions() as db:
            row = await db.scalar(query)
            return None if row is None else _feedback_from_row(row)

    async def list_by_session(self, session_id: str) -> list[Feedback]:
        query = (
            select(FeedbackRow)
            .where(FeedbackRow.session_id == session_id)
            .order_by(FeedbackRow.created_at, FeedbackRow.id)
        )
        async with self._sessions() as db:
            rows = (await db.scalars(query)).all()
            return [_feedback_from_row(row) for row in rows]

    async def delete_for_message(self, session_id: str, message_id: str) -> bool:
        async with self._sessions.begin() as db:
            row = await db.scalar(
                select(FeedbackRow).where(
                    FeedbackRow.session_id == session_id,
                    FeedbackRow.message_id == message_id,
                )
            )
            if row is None:
                return False
            await db.delete(row)
            return True

    async def delete_by_session(self, session_id: str) -> None:
        async with self._sessions.begin() as db:
            rows = await db.scalars(
                select(FeedbackRow).where(FeedbackRow.session_id == session_id)
            )
            for row in rows:
                await db.delete(row)


class SQLiteRepositories:
    """Shared SQLite engine and repositories with explicit async disposal."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        self.sessions = SQLAlchemySessionRepository(self.sessionmaker)
        self.transcripts = SQLAlchemyTranscriptRepository(self.sessionmaker)
        self.feedback = SQLAlchemyFeedbackRepository(self.sessionmaker)

    @classmethod
    async def open(
        cls,
        database_url: str,
        *,
        migrate: bool = True,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> SQLiteRepositories:
        engine = create_sqlite_engine(
            database_url, busy_timeout_ms=busy_timeout_ms
        )
        bundle = cls(engine)
        try:
            if migrate:
                await upgrade_database(engine)
        except BaseException:
            await engine.dispose()
            raise
        return bundle

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def __aenter__(self) -> SQLiteRepositories:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.dispose()


@contextmanager
def _migration_config(connection: Connection | None = None) -> Iterator[Config]:
    migrations = resources.files("agent_chat_minimal").joinpath("migrations")
    with resources.as_file(migrations) as migration_path:
        config = Config()
        config.set_main_option("script_location", str(migration_path))
        if connection is not None:
            config.attributes["connection"] = connection
        yield config


async def upgrade_database(engine: AsyncEngine, revision: str = "head") -> None:
    """Upgrade a database using the caller-owned async engine."""

    def upgrade(connection: Connection) -> None:
        with _migration_config(connection) as config:
            command.upgrade(config, revision)

    async with engine.begin() as connection:
        await connection.run_sync(upgrade)


async def current_database_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as connection:
        if not await connection.run_sync(_has_version_table):
            return None
        return await connection.scalar(text("SELECT version_num FROM alembic_version"))


def _has_version_table(connection: Connection) -> bool:
    return connection.dialect.has_table(connection, "alembic_version")


def migration_head() -> str:
    with _migration_config() as config:
        return ScriptDirectory.from_config(config).get_current_head()


def migration_main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade the application database")
    parser.add_argument("database", help="SQLite path or sqlite+aiosqlite URL")
    args = parser.parse_args()

    async def migrate() -> None:
        database_url = (
            args.database
            if args.database.startswith("sqlite+aiosqlite:///")
            else sqlite_url(args.database)
        )
        engine = create_sqlite_engine(database_url)
        try:
            await upgrade_database(engine)
        finally:
            await engine.dispose()

    asyncio.run(migrate())


__all__ = [
    "DEFAULT_BUSY_TIMEOUT_MS",
    "SQLAlchemyFeedbackRepository",
    "SQLAlchemySessionRepository",
    "SQLAlchemyTranscriptRepository",
    "SQLiteRepositories",
    "create_sqlite_engine",
    "current_database_revision",
    "migration_head",
    "migration_main",
    "sqlite_url",
    "upgrade_database",
]
