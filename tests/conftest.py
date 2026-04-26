"""
shared pytest fixtures — mock HTML and in-memory DB for all test modules.
"""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
import aiosqlite

# Ensure backend/ is on the path so imports work from tests/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Point settings at test values before any backend import triggers config load
os.environ.setdefault("ROUTER_IP", "192.168.100.1")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("POLL_INTERVAL", "30")
os.environ.setdefault("WEBHOOK_URLS", "")
os.environ.setdefault("SMTP_HOST", "")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def html_downstream() -> str:
    return (FIXTURES / "hub5_downstream.html").read_text()


@pytest.fixture
def html_upstream() -> str:
    return (FIXTURES / "hub5_upstream.html").read_text()


@pytest.fixture
def html_event_log() -> str:
    return (FIXTURES / "hub5_event_log.html").read_text()


@pytest.fixture
def html_wan() -> str:
    return (FIXTURES / "hub5_wan.html").read_text()


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite DB seeded with the full schema."""
    from database import SCHEMA
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(SCHEMA)
        await conn.commit()
        yield conn
