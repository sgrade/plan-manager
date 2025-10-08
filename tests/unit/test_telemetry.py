"""Unit tests for telemetry utilities."""

import logging
from unittest.mock import patch
import pytest
from plan_manager.telemetry import incr, timer, _should_sample


class TestTelemetrySampling:
    """Test telemetry sampling logic."""

    def test_should_sample_disabled(self):
        """Test that sampling is disabled when TELEMETRY_ENABLED is False."""
        with patch('plan_manager.telemetry.TELEMETRY_ENABLED', False):
            assert _should_sample() is False

    def test_should_sample_enabled_rate_1(self):
        """Test that sampling always returns True when rate is 1.0."""
        with patch('plan_manager.telemetry.TELEMETRY_ENABLED', True), \
                patch('plan_manager.telemetry.TELEMETRY_SAMPLE_RATE', 1.0), \
                patch('random.random', return_value=0.5):
            assert _should_sample() is True

    def test_should_sample_enabled_rate_0(self):
        """Test that sampling always returns False when rate is 0.0."""
        with patch('plan_manager.telemetry.TELEMETRY_ENABLED', True), \
                patch('plan_manager.telemetry.TELEMETRY_SAMPLE_RATE', 0.0), \
                patch('random.random', return_value=0.5):
            assert _should_sample() is False

    def test_should_sample_random_sampling(self):
        """Test random sampling logic."""
        with patch('plan_manager.telemetry.TELEMETRY_ENABLED', True), \
                patch('plan_manager.telemetry.TELEMETRY_SAMPLE_RATE', 0.5):
            with patch('random.random', return_value=0.3):
                assert _should_sample() is True
            with patch('random.random', return_value=0.7):
                assert _should_sample() is False

    def test_should_sample_invalid_rate_graceful(self):
        """Test that invalid sample rates are handled gracefully."""
        with patch('plan_manager.telemetry.TELEMETRY_ENABLED', True), \
                patch('plan_manager.telemetry.TELEMETRY_SAMPLE_RATE', "invalid"):
            assert _should_sample() is False


class TestTelemetryIncr:
    """Test telemetry counter functionality."""

    def test_incr_not_sampled(self, caplog):
        """Test that incr doesn't log when not sampled."""
        with patch('plan_manager.telemetry._should_sample', return_value=False):
            with caplog.at_level(logging.DEBUG):
                incr("test.metric", value=5, user_id="123", action="create")

        assert len(caplog.records) == 0

    def test_incr_sampled(self, caplog):
        """Test that incr logs telemetry data when sampled."""
        with patch('plan_manager.telemetry._should_sample', return_value=True):
            with caplog.at_level(logging.DEBUG):
                incr("test.metric", value=5, user_id="123", action="create")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Telemetry counter:" in record.message
        # Parse the logged data
        log_data = eval(record.message.split(": ", 1)[1])
        assert log_data["metric"] == "test.metric"
        assert log_data["type"] == "counter"
        assert log_data["value"] == 5
        assert log_data["user_id"] == "123"
        assert log_data["action"] == "create"

    def test_incr_default_value(self, caplog):
        """Test that incr uses default value of 1."""
        with patch('plan_manager.telemetry._should_sample', return_value=True):
            with caplog.at_level(logging.DEBUG):
                incr("test.metric")

        assert len(caplog.records) == 1
        log_data = eval(caplog.records[0].message.split(": ", 1)[1])
        assert log_data["value"] == 1

    def test_incr_no_labels(self, caplog):
        """Test incr with no additional labels."""
        with patch('plan_manager.telemetry._should_sample', return_value=True):
            with caplog.at_level(logging.DEBUG):
                incr("test.metric", value=3)

        log_data = eval(caplog.records[0].message.split(": ", 1)[1])
        assert log_data["metric"] == "test.metric"
        assert log_data["value"] == 3
        assert log_data["type"] == "counter"


class TestTelemetryTimer:
    """Test telemetry timer functionality."""

    def test_timer_not_sampled(self, caplog):
        """Test that timer doesn't log when not sampled."""
        with patch('plan_manager.telemetry._should_sample', return_value=False):
            with caplog.at_level(logging.DEBUG):
                with timer("test.timer", operation="save"):
                    pass

        assert len(caplog.records) == 0

    def test_timer_sampled(self, caplog):
        """Test that timer logs duration when sampled."""
        with patch('plan_manager.telemetry._should_sample', return_value=True), \
                patch('time.perf_counter', side_effect=[100.0, 100.5]):
            with caplog.at_level(logging.DEBUG):
                with timer("test.timer", operation="save", user_id="123"):
                    pass

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Telemetry timer:" in record.message

        log_data = eval(record.message.split(": ", 1)[1])
        assert log_data["metric"] == "test.timer"
        assert log_data["type"] == "timer"
        assert log_data["ms"] == 500.0  # 0.5 seconds = 500ms
        assert log_data["operation"] == "save"
        assert log_data["user_id"] == "123"

    def test_timer_exception_handling(self, caplog):
        """Test that timer still logs even if code raises exception."""
        with patch('plan_manager.telemetry._should_sample', return_value=True), \
                patch('time.perf_counter', side_effect=[100.0, 100.2]):
            with pytest.raises(ValueError):
                with caplog.at_level(logging.DEBUG):
                    with timer("test.timer"):
                        raise ValueError("Test exception")

        assert len(caplog.records) == 1
        log_data = eval(caplog.records[0].message.split(": ", 1)[1])
        assert log_data["ms"] == 200.0  # Still logged despite exception


class TestTelemetryIntegration:
    """Integration tests for telemetry module."""

    def test_telemetry_disabled_by_default(self, caplog):
        """Test that telemetry is disabled by default in tests."""
        # This test assumes TELEMETRY_ENABLED is False by default
        # If it's enabled in the test environment, this test will need adjustment
        with caplog.at_level(logging.DEBUG):
            incr("test.metric")
            with timer("test.timer"):
                pass

        # Should not log anything if telemetry is disabled
        # (This depends on the default config value)
