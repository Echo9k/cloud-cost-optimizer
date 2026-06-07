"""Persistence wiring (SQLAlchemy + SQLite).

This module owns the engine/session and the ORM Base. It is deliberately
separate from the Pydantic API-contract models in `app/models.py`: persistence
rows (`app/orm.py`) and API schemas are different concerns and must not fuse.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# SQLite file at the repo root. Gitignored (*.db).
_DB_PATH = Path(__file__).resolve().parent.parent / "cost_optimizer.db"
_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM persistence models."""


def init_db() -> None:
    """Create tables if they do not exist. Importing orm registers the models."""
    from app import orm  # noqa: F401  (side-effect: table registration)

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session, always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
