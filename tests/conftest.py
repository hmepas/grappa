"""Common test fixtures."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_settings():
    """Mock application settings for testing."""
    # Create simple mock objects instead of actual pydantic settings
    telegram_mock = Mock()
    telegram_mock.api_id = 123456
    telegram_mock.api_hash = "test_hash"
    telegram_mock.phone_number = "+1234567890"
    telegram_mock.session_name = "test_session"

    app_mock = Mock()
    app_mock.debug = True
    app_mock.log_level = "DEBUG"
    app_mock.data_dir = Path("/tmp/grappa_test/data")
    app_mock.session_dir = Path("/tmp/grappa_test/sessions")
    app_mock.max_messages_per_chat = 1000
    app_mock.context_length = 100

    settings_mock = Mock()
    settings_mock.telegram = telegram_mock
    settings_mock.app = app_mock

    return settings_mock


@pytest.fixture
def mock_pyrogram_client():
    """Mock Pyrogram client for testing."""
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.get_me = AsyncMock()
    client.get_dialogs = AsyncMock()
    client.get_chat = AsyncMock()
    return client
