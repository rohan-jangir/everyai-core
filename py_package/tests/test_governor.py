"""Unit tests for the Local Rate Limit Governor.

Verifies request and token throttling, sliding window record cleaning,
and sleeps when RPM or TPM limits are exceeded.
"""

import time
import pytest
from everyai_core.governor import RateLimitGovernor


def test_governor_disabled_by_default():
    """Verify governor does nothing when limit thresholds are not set."""
    gov = RateLimitGovernor()
    # Should run instantly without error or sleep
    gov.throttle_if_needed(estimated_tokens=50000)
    assert len(gov.history) == 0

    gov.record_request(1000)
    assert len(gov.history) == 0


def test_governor_rpm_throttling(monkeypatch):
    """Test governor throttles based on requests-per-minute (RPM) limits."""
    gov = RateLimitGovernor(max_requests_per_minute=2)

    sleep_calls = []
    current_mock_time = 1000.0

    monkeypatch.setattr(time, "sleep", lambda t: sleep_calls.append(t))
    monkeypatch.setattr(time, "time", lambda: current_mock_time)

    # First request
    gov.throttle_if_needed(estimated_tokens=10)
    gov.record_request(tokens_used=10)
    assert len(gov.history) == 1
    assert len(sleep_calls) == 0

    # Second request
    gov.throttle_if_needed(estimated_tokens=10)
    gov.record_request(tokens_used=10)
    assert len(gov.history) == 2
    assert len(sleep_calls) == 0

    # Third request - exceeds RPM limit. Should sleep to wait for window shift.
    # The oldest request was recorded at current_mock_time = 1000.0.
    # The throttle window shifts past it at 1000.0 + 60.0 = 1060.0.
    # So it should sleep for (1000.0 + 60.0) - 1000.0 = 60.0 seconds.
    # But wait, throttle_if_needed does a loop. To avoid infinite loop in mock:
    # We will advance the mock time inside time.sleep mock, or let it advance!
    def mock_sleep(t):
        nonlocal current_mock_time
        sleep_calls.append(t)
        current_mock_time += t

    monkeypatch.setattr(time, "sleep", mock_sleep)

    gov.throttle_if_needed(estimated_tokens=10)
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(60.0)


def test_governor_tpm_throttling(monkeypatch):
    """Test governor throttles based on tokens-per-minute (TPM) limits."""
    gov = RateLimitGovernor(max_tokens_per_minute=1000)

    sleep_calls = []
    current_mock_time = 1000.0

    def mock_sleep(t):
        nonlocal current_mock_time
        sleep_calls.append(t)
        current_mock_time += t

    monkeypatch.setattr(time, "sleep", mock_sleep)
    monkeypatch.setattr(time, "time", lambda: current_mock_time)

    # First request: uses 600 tokens
    gov.throttle_if_needed(estimated_tokens=600)
    gov.record_request(tokens_used=600)
    assert len(sleep_calls) == 0

    # Second request: needs 500 tokens (600 + 500 > 1000 limit). Should throttle.
    gov.throttle_if_needed(estimated_tokens=500)
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(60.0)


def test_governor_sliding_window_cleanup(monkeypatch):
    """Verify governor cleans history outside the 60 second sliding window."""
    gov = RateLimitGovernor(max_requests_per_minute=2)

    current_mock_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_mock_time)

    gov.record_request(tokens_used=10)
    
    # Fast forward time by 61 seconds
    current_mock_time = 1061.0

    gov._clean_old_records(current_mock_time)
    assert len(gov.history) == 0
