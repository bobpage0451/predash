"""Database engine and session factory."""

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEFAULT_DATABASE_URL = "postgresql+psycopg://presence:presence@postgres:5432/presence"


@lru_cache(maxsize=1)
def get_engine():
    """Return a cached SQLAlchemy engine.

    Reads DATABASE_URL from the environment, falling back to the default.
    The ``+psycopg`` dialect targets psycopg 3.
    """
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    # Ensure we use the psycopg (v3) driver even if the env var uses the
    # bare ``postgresql://`` scheme.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, echo=False, pool_pre_ping=True)


def get_session():
    """Return a sessionmaker bound to the default engine."""
    return sessionmaker(bind=get_engine())
