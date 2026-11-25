import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from enterprise_knowledge_copilot.db import Base

os.environ.setdefault("DATABASE_URL", "postgresql://app:secret@localhost:5432/app")
os.environ.setdefault("REDIS_URL", "redis://:secret@localhost:6379/0")


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    engine = create_engine("sqlite://")
    if engine.dialect.name == "sqlite":
        event.listen(
            engine,
            "connect",
            lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
        )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session
