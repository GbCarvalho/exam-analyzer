import os
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from sqlmodel import SQLModel
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from main import app  # noqa: E402
from storage.database import get_session  # noqa: E402

# Import models so metadata is populated
import models.db  # noqa: F401


@asynccontextmanager
async def _noop_lifespan(app):
    """Skip DB migrations in tests — SQLite tables are created by the session fixture."""
    yield


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Enforce FK constraints in SQLite (matches Postgres behavior)
    @event.listens_for(engine.sync_engine, "connect")
    def set_fk_pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client(session):
    async def override_get_session():
        yield session

    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
