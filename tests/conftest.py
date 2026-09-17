import pytest
from datetime import datetime, timezone

from capabilities.capabilities import CapabilityService
from capabilities.repository.sqlite_repository import SQLiteRepository
from capabilities.repository.clock import Clock
from config.config import config

@pytest.fixture
def service():
    repo = SQLiteRepository(config.db_path)     
    clock = Clock(as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc))
    return CapabilityService(repository=repo, clock=clock, config=config) 