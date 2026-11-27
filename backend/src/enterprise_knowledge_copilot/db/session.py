from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from enterprise_knowledge_copilot.db.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_database(database_url: str) -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_engine(database_url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        raise RuntimeError("Database is not configured.")
    return _session_factory


def get_db(request: Request) -> Iterator[Session]:
    app_session = getattr(request.app.state, "db_session", None)
    if callable(app_session):
        session_factory = app_session
    elif app_session is None:
        session_factory = get_session_factory()
    else:
        session_factory = app_session

    if callable(session_factory) and hasattr(session_factory, "close_all"):
        raise RuntimeError("Expected a SQLAlchemy session factory.")
    with session_factory() as session:
        yield session


def create_database_tables(database_url: str) -> None:
    engine = configure_database(database_url)
    Base.metadata.create_all(engine)
