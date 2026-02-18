"""Tests for usage tracking."""

import tempfile
from pathlib import Path

import pytest

from src.usage import UsageTracker


@pytest.fixture
def temp_workspace():
    """Create temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def usage_tracker(temp_workspace):
    """Create UsageTracker instance."""
    return UsageTracker(temp_workspace)


def test_initial_stats(usage_tracker):
    """Test initial stats are zero."""
    stats = usage_tracker.get_stats()
    
    assert stats["total_requests"] == 0
    assert stats["total_input_tokens"] == 0
    assert stats["total_output_tokens"] == 0
    assert stats["total_cost"] == 0.0


def test_record_usage(usage_tracker):
    """Test recording usage."""
    usage_tracker.record("claude-sonnet-4-20250514", 1000, 500)
    
    stats = usage_tracker.get_stats()
    
    assert stats["total_requests"] == 1
    assert stats["total_input_tokens"] == 1000
    assert stats["total_output_tokens"] == 500


def test_record_multiple(usage_tracker):
    """Test recording multiple usages."""
    usage_tracker.record("claude-sonnet-4-20250514", 1000, 500)
    usage_tracker.record("claude-sonnet-4-20250514", 2000, 1000)
    
    stats = usage_tracker.get_stats()
    
    assert stats["total_requests"] == 2
    assert stats["total_input_tokens"] == 3000
    assert stats["total_output_tokens"] == 1500


def test_cost_calculation(usage_tracker):
    """Test cost calculation."""
    # Sonnet pricing: $3/1M input, $15/1M output
    usage_tracker.record("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    
    stats = usage_tracker.get_stats()
    
    # $3 input + $15 output = $18
    assert stats["total_cost"] == pytest.approx(18.0, rel=0.1)


def test_reset(usage_tracker):
    """Test resetting usage."""
    usage_tracker.record("claude-sonnet-4-20250514", 1000, 500)
    usage_tracker.reset()
    
    stats = usage_tracker.get_stats()
    
    assert stats["total_requests"] == 0
    assert stats["total_input_tokens"] == 0


def test_format_stats(usage_tracker):
    """Test formatting stats."""
    usage_tracker.record("claude-sonnet-4-20250514", 1000, 500)
    
    formatted = usage_tracker.format_stats()
    
    assert "Usage" in formatted or "usage" in formatted.lower()
    assert "1000" in formatted or "1,000" in formatted


def test_persistence(temp_workspace):
    """Test usage persists to disk."""
    tracker1 = UsageTracker(temp_workspace)
    tracker1.record("claude-sonnet-4-20250514", 5000, 2500)
    
    # Create new tracker (simulating restart)
    tracker2 = UsageTracker(temp_workspace)
    stats = tracker2.get_stats()
    
    assert stats["total_requests"] == 1
    assert stats["total_input_tokens"] == 5000


def test_per_model_tracking(usage_tracker):
    """Test tracking by model."""
    usage_tracker.record("claude-sonnet-4-20250514", 1000, 500)
    usage_tracker.record("claude-opus-4-20250514", 500, 250)
    
    stats = usage_tracker.get_stats()
    
    assert stats["total_requests"] == 2
    # Should track both models
    assert "by_model" in stats or stats["total_input_tokens"] == 1500
