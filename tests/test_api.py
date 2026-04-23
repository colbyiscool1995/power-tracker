import os
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from power_tracker.api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


_SENTINEL = object()


def _mock_conn(rows=None, scalar=_SENTINEL):
    cur = MagicMock()
    if scalar is not _SENTINEL:
        cur.fetchone.return_value = (scalar,)
    else:
        cur.fetchall.return_value = rows or []
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


_TS = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
_DATE = date(2026, 4, 22)


@patch("power_tracker.api.get_connection")
def test_get_readings(mock_gc, client):
    mock_gc.return_value = _mock_conn(rows=[("chip/PPT", 50.0, _TS)])
    res = client.get("/readings")
    assert res.status_code == 200
    data = res.get_json()
    assert data[0]["source"] == "chip/PPT"
    assert data[0]["watts"] == 50.0


@patch("power_tracker.api.get_connection")
def test_get_readings_empty(mock_gc, client):
    mock_gc.return_value = _mock_conn(rows=[])
    res = client.get("/readings")
    assert res.status_code == 200
    assert res.get_json() == []


@patch("power_tracker.api.get_connection")
def test_get_current_total(mock_gc, client):
    mock_gc.return_value = _mock_conn(scalar=123.5)
    res = client.get("/totals/current")
    assert res.status_code == 200
    assert res.get_json()["total_watts"] == 123.5


@patch("power_tracker.api.get_connection")
def test_get_current_total_empty(mock_gc, client):
    mock_gc.return_value = _mock_conn(scalar=None)
    res = client.get("/totals/current")
    assert res.get_json()["total_watts"] == 0.0


@patch("power_tracker.api.get_connection")
def test_get_lifetime_kwh(mock_gc, client):
    mock_gc.return_value = _mock_conn(scalar=9.6)
    res = client.get("/totals/lifetime_kwh")
    assert res.status_code == 200
    assert res.get_json()["lifetime_kwh"] == 9.6


@patch("power_tracker.api.get_connection")
def test_get_monthly_wh_current_month(mock_gc, client):
    mock_gc.return_value = _mock_conn(scalar=2400.0)
    with patch.dict(os.environ, {"BILLING_DAY": "1"}):
        with patch("power_tracker.api.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 22)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            res = client.get("/totals/monthly_wh")
    assert res.status_code == 200
    body = res.get_json()
    assert body["wh"] == 2400.0
    assert body["period_start"] == "2026-04-01"
    assert body["period_end"] == "2026-04-22"


@patch("power_tracker.api.get_connection")
def test_get_monthly_wh_previous_month(mock_gc, client):
    # billing day 25, today is 10th → period starts 25th of previous month
    mock_gc.return_value = _mock_conn(scalar=1000.0)
    with patch.dict(os.environ, {"BILLING_DAY": "25"}):
        with patch("power_tracker.api.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 10)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            res = client.get("/totals/monthly_wh")
    assert res.status_code == 200
    body = res.get_json()
    assert body["period_start"] == "2026-03-25"


@patch("power_tracker.api.get_connection")
def test_get_daily_totals(mock_gc, client):
    mock_gc.return_value = _mock_conn(rows=[(_DATE, 200.0)])
    res = client.get("/totals/daily")
    assert res.status_code == 200
    data = res.get_json()
    assert data[0]["total_watts"] == 200.0
    assert data[0]["day"] == "2026-04-22"

@patch("power_tracker.api.get_connection")
def test_get_current_watts(mock_gc, client):
    mock_gc.return_value = _mock_conn(scalar=75.0)
    res = client.get("/totals/current_watts")
    assert res.status_code == 200
    assert res.get_json()["current_watts"] == 75.0

@patch("power_tracker.api.get_connection")
def test_get_kwh_per_day(mock_gc, client):
    mock_gc.return_value = _mock_conn(rows=[(_DATE, 1.5)])
    res = client.get("/totals/kwh_per_day")
    assert res.status_code == 200
    data = res.get_json()
    assert data[0]["day"] == "2026-04-22"
    assert data[0]["kwh"] == 1.5