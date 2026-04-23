from unittest.mock import MagicMock, call, patch

import pytest

import power_tracker.database as db


def _mock_conn(fetchone_return=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_return
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cur


@patch("power_tracker.database.get_connection")
def test_insert_wattage_reading(mock_get_conn):
    conn, cur = _mock_conn()
    mock_get_conn.return_value = conn

    db.insert_wattage_reading("chip/PPT", 50.0)

    cur.execute.assert_called_once()
    sql, params = cur.execute.call_args.args
    assert "INSERT INTO wattage_readings" in sql
    assert params == ("chip/PPT", 50.0)
    conn.commit.assert_called_once()


@patch("power_tracker.database.get_connection")
def test_flush_residual_no_rows(mock_get_conn):
    conn, cur = _mock_conn(fetchone_return=(0,))
    mock_get_conn.return_value = conn

    db._flush_residual_readings()

    # only the COUNT query, no INSERT or DELETE
    assert cur.execute.call_count == 1
    assert "COUNT" in cur.execute.call_args.args[0]


@patch("power_tracker.database.get_connection")
def test_flush_residual_with_rows(mock_get_conn):
    conn, cur = _mock_conn(fetchone_return=(3,))
    mock_get_conn.return_value = conn

    db._flush_residual_readings()

    calls = [c.args[0] for c in cur.execute.call_args_list]
    assert any("COUNT" in s for s in calls)
    assert any("INSERT INTO wattage_averages" in s for s in calls)
    assert any("DELETE FROM wattage_readings" in s for s in calls)
    conn.commit.assert_called_once()


@patch("power_tracker.database.get_connection")
def test_rollup_minute_averages(mock_get_conn):
    conn, cur = _mock_conn()
    mock_get_conn.return_value = conn

    db.rollup_minute_averages()

    calls = [c.args[0] for c in cur.execute.call_args_list]
    assert any("INSERT INTO wattage_averages" in s for s in calls)
    assert any("DELETE FROM wattage_readings" in s for s in calls)
    conn.commit.assert_called_once()


@patch("power_tracker.database.get_connection")
def test_rollup_hourly_averages(mock_get_conn):
    conn, cur = _mock_conn()
    mock_get_conn.return_value = conn

    db.rollup_hourly_averages()

    calls = [c.args[0] for c in cur.execute.call_args_list]
    assert any("INSERT INTO wattage_hourly" in s for s in calls)
    assert any("ON CONFLICT" in s for s in calls)
    conn.commit.assert_called_once()


@patch("power_tracker.database.get_connection")
def test_rollup_daily_averages(mock_get_conn):
    conn, cur = _mock_conn()
    mock_get_conn.return_value = conn

    db.rollup_daily_averages()

    calls = [c.args[0] for c in cur.execute.call_args_list]
    assert any("INSERT INTO wattage_daily" in s for s in calls)
    conn.commit.assert_called_once()
