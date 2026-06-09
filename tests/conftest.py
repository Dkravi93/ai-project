"""
Pytest configuration and fixtures.
"""
import pytest
from config.settings import get_settings

@pytest.fixture
def settings():
    """Provide settings for tests."""
    return get_settings()
