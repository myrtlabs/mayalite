"""Tests for reminder system."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from src.reminders import ReminderManager, Reminder


@pytest.fixture
def temp_workspace():
    """Create temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_scheduler():
    """Create mock scheduler."""
    scheduler = MagicMock()
    scheduler.add_job = MagicMock(return_value=MagicMock(id="test-job-id"))
    return scheduler


@pytest.fixture
def reminder_manager(temp_workspace, mock_scheduler):
    """Create ReminderManager with mocks."""
    send_callback = AsyncMock()
    return ReminderManager(
        workspace_path=temp_workspace,
        scheduler=mock_scheduler,
        send_callback=send_callback,
    )


def test_create_reminder_in_hours(reminder_manager):
    """Test creating reminder with 'in X hours'."""
    reminder = reminder_manager.create_reminder(
        user_id=123,
        chat_id=456,
        time_str="in 2 hours",
        message="Test reminder",
        workspace="main",
    )
    
    assert reminder is not None
    assert reminder.message == "Test reminder"
    assert reminder.user_id == 123
    assert reminder.chat_id == 456


def test_create_reminder_tomorrow(reminder_manager):
    """Test creating reminder for tomorrow."""
    reminder = reminder_manager.create_reminder(
        user_id=123,
        chat_id=456,
        time_str="tomorrow at 9am",
        message="Morning meeting",
        workspace="main",
    )
    
    assert reminder is not None
    assert reminder.message == "Morning meeting"


def test_list_reminders_empty(reminder_manager):
    """Test listing reminders when none exist."""
    reminders = reminder_manager.list_reminders(user_id=123)
    
    assert reminders == []


def test_list_reminders_after_create(reminder_manager):
    """Test listing reminders after creating one."""
    reminder_manager.create_reminder(
        user_id=123,
        chat_id=456,
        time_str="in 1 hour",
        message="Test",
        workspace="main",
    )
    
    reminders = reminder_manager.list_reminders(user_id=123)
    
    assert len(reminders) == 1


def test_format_reminder_list_empty(reminder_manager):
    """Test formatting empty reminder list."""
    formatted = reminder_manager.format_reminder_list([])
    
    assert "No pending" in formatted or "empty" in formatted.lower()


def test_format_reminder_list_with_items(reminder_manager):
    """Test formatting reminder list with items."""
    reminder_manager.create_reminder(
        user_id=123,
        chat_id=456,
        time_str="in 1 hour",
        message="Test reminder",
        workspace="main",
    )
    
    reminders = reminder_manager.list_reminders(user_id=123)
    formatted = reminder_manager.format_reminder_list(reminders)
    
    assert "Test reminder" in formatted


def test_reminder_persistence(temp_workspace, mock_scheduler):
    """Test reminders persist to disk."""
    send_callback = AsyncMock()
    
    # Create manager and add reminder
    manager1 = ReminderManager(temp_workspace, mock_scheduler, send_callback)
    manager1.create_reminder(
        user_id=123,
        chat_id=456,
        time_str="in 2 hours",
        message="Persistent reminder",
        workspace="main",
    )
    
    # Create new manager (simulating restart)
    manager2 = ReminderManager(temp_workspace, mock_scheduler, send_callback)
    reminders = manager2.list_reminders(user_id=123)
    
    # Should still have the reminder
    assert len(reminders) == 1
    assert reminders[0].message == "Persistent reminder"
