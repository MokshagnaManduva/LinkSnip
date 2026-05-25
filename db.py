"""
db.py - Database layer for the URL Shortener
=============================================
Provides:
  - SQLAlchemy engine & scoped session (thread-safe)
  - URL model mapped to the `urls` table
  - init_db()  → creates tables if they don't exist
  - get_db()   → returns the current scoped session
  - shutdown_session() → cleanup hook for Flask teardown
"""

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    scoped_session,
    sessionmaker,
)
from sqlalchemy.pool import NullPool


# =============================================================================
# Engine & Session Factory
# =============================================================================

# Read the connection string from the environment.
# Falls back to a local SQLite file so the app works without any config.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///urls.db")

# Neon and some other providers emit "postgres://" but SQLAlchemy 2.x
# only accepts "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Use pg8000 (pure-Python driver) so the app works on Vercel's build env
# where psycopg2 binary wheels are unavailable.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

# For SQLite we need check_same_thread=False to allow Flask's multi-threaded
# request handling. For MySQL/PostgreSQL this kwarg is silently ignored.
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # NullPool avoids connection leaks in serverless environments (Vercel)
    # where processes are recycled unpredictably.
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    **engine_kwargs,
)

# scoped_session gives each thread its own Session, preventing cross-thread
# state corruption in a multi-threaded WSGI server (gunicorn, etc.).
session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
db_session = scoped_session(session_factory)


# =============================================================================
# Declarative Base & Model
# =============================================================================

class Base(DeclarativeBase):
    """Modern SQLAlchemy 2.0 declarative base."""
    pass


class URL(Base):
    """
    Represents a shortened URL entry.

    Attributes:
        id           – Auto-incrementing primary key.
        short_id     – The unique short identifier (e.g. "aB3xZ9" or custom alias).
        original_url – The full destination URL the short link redirects to.
        click_count  – Number of times the short link has been visited.
        created_at   – UTC timestamp of when the link was created.
    """

    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_id = Column(String(30), unique=True, nullable=False, index=True)
    original_url = Column(Text, nullable=False)
    click_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<URL(id={self.id}, short_id='{self.short_id}', "
            f"clicks={self.click_count})>"
        )

    def to_dict(self) -> dict:
        """Serialize the model to a JSON-friendly dictionary."""
        return {
            "short_id": self.short_id,
            "original_url": self.original_url,
            "click_count": self.click_count,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }


# =============================================================================
# Helper Functions
# =============================================================================

def init_db() -> None:
    """
    Create all tables defined by the Base metadata.

    Safe to call multiple times — SQLAlchemy's create_all() is a no-op for
    tables that already exist.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Return the current thread-local database session.

    Usage in Flask route handlers:
        session = get_db()
        session.add(url_obj)
        session.commit()
    """
    return db_session


def shutdown_session(exception=None) -> None:
    """
    Remove the scoped session at the end of a request.

    Register this with Flask:
        app.teardown_appcontext(shutdown_session)

    This ensures connections are returned to the pool and any uncommitted
    transactions are rolled back.
    """
    db_session.remove()
