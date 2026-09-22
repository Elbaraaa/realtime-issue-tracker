from collections.abc import Callable, Iterator

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session_factory() -> Callable[[], Session]:
    """Overridden in tests. WebSocket handlers use this to open short-lived sessions
    instead of holding a pooled connection for the life of the socket."""
    return SessionLocal


def get_db(factory: Callable[[], Session] = Depends(get_session_factory)) -> Iterator[Session]:
    with factory() as session:
        yield session
