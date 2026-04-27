import json
from unittest.mock import MagicMock, patch

import pytest

from power_tracker.consumer import _on_message


def _make_method(tag=1):
    method = MagicMock()
    method.delivery_tag = tag
    return method


def _make_channel():
    return MagicMock()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@patch("power_tracker.consumer.insert_wattage_reading")
def test_valid_message_acks_and_inserts(mock_insert):
    channel = _make_channel()
    method = _make_method()
    body = json.dumps({"source": "chip/PPT", "watts": 42.5,
                       "system_name": "my-host", "local_ip": "192.168.1.1"})

    _on_message(channel, method, None, body.encode())

    mock_insert.assert_called_once_with("chip/PPT", 42.5, "my-host", "192.168.1.1")
    channel.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)
    channel.basic_nack.assert_not_called()


@patch("power_tracker.consumer.insert_wattage_reading")
def test_valid_message_optional_fields_default_empty(mock_insert):
    """system_name and local_ip should default to '' when absent."""
    channel = _make_channel()
    method = _make_method()
    body = json.dumps({"source": "chip/PPT", "watts": 10.0})

    _on_message(channel, method, None, body.encode())

    mock_insert.assert_called_once_with("chip/PPT", 10.0, "", "")
    channel.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)
    channel.basic_nack.assert_not_called()


# ---------------------------------------------------------------------------
# Invalid payload — must nack without requeue
# ---------------------------------------------------------------------------

def test_invalid_json_nacks_without_requeue():
    channel = _make_channel()
    method = _make_method()

    _on_message(channel, method, None, b"not-valid-json")

    channel.basic_nack.assert_called_once_with(
        delivery_tag=method.delivery_tag, requeue=False
    )
    channel.basic_ack.assert_not_called()


def test_missing_source_key_nacks_without_requeue():
    channel = _make_channel()
    method = _make_method()
    body = json.dumps({"watts": 99.0})

    _on_message(channel, method, None, body.encode())

    channel.basic_nack.assert_called_once_with(
        delivery_tag=method.delivery_tag, requeue=False
    )
    channel.basic_ack.assert_not_called()


def test_missing_watts_key_nacks_without_requeue():
    channel = _make_channel()
    method = _make_method()
    body = json.dumps({"source": "chip/PPT"})

    _on_message(channel, method, None, body.encode())

    channel.basic_nack.assert_called_once_with(
        delivery_tag=method.delivery_tag, requeue=False
    )
    channel.basic_ack.assert_not_called()


def test_non_float_watts_nacks_without_requeue():
    channel = _make_channel()
    method = _make_method()
    body = json.dumps({"source": "chip/PPT", "watts": "not-a-number"})

    _on_message(channel, method, None, body.encode())

    channel.basic_nack.assert_called_once_with(
        delivery_tag=method.delivery_tag, requeue=False
    )
    channel.basic_ack.assert_not_called()


# ---------------------------------------------------------------------------
# Transient / operational errors
# ---------------------------------------------------------------------------

@patch("power_tracker.consumer.insert_wattage_reading",
       side_effect=Exception("DB connection refused"))
def test_db_error_nacks(mock_insert):
    """DB / operational errors must nack so the message is not silently lost.

    The current implementation always nacks with requeue=False for any
    exception.  A future improvement could requeue on transient errors.
    """
    channel = _make_channel()
    method = _make_method()
    body = json.dumps({"source": "chip/PPT", "watts": 5.0})

    _on_message(channel, method, None, body.encode())

    channel.basic_nack.assert_called_once_with(
        delivery_tag=method.delivery_tag, requeue=False
    )
    channel.basic_ack.assert_not_called()
