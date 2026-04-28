import json
import os
from datetime import date, timedelta

from flask import Flask, jsonify

from power_tracker.database import get_connection

app = Flask(__name__)


@app.route("/readings")
def get_readings():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, watts, timestamp
                FROM wattage_readings
                ORDER BY timestamp DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"source": r[0], "watts": r[1], "timestamp": r[2].isoformat()}
        for r in rows
    ])


@app.route("/averages/minute")
def get_minute_averages():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, avg_watts, minute
                FROM wattage_averages
                ORDER BY minute DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"source": r[0], "avg_watts": r[1], "minute": r[2].isoformat()}
        for r in rows
    ])


@app.route("/averages/hourly")
def get_hourly_averages():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, avg_watts, hour
                FROM wattage_hourly
                ORDER BY hour DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"source": r[0], "avg_watts": r[1], "hour": r[2].isoformat()}
        for r in rows
    ])


@app.route("/averages/daily")
def get_daily_averages():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, avg_watts, day
                FROM wattage_daily
                ORDER BY day DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"source": r[0], "avg_watts": r[1], "day": r[2].isoformat()}
        for r in rows
    ])


@app.route("/totals/current")
def get_current_total():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, SUM(watts)
                FROM wattage_readings
                GROUP BY system_name
                ORDER BY system_name;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "total_watts": r[1]}
        for r in rows
    ])


@app.route("/totals/minute")
def get_minute_totals():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, minute, SUM(avg_watts)
                FROM wattage_averages
                GROUP BY system_name, minute
                ORDER BY system_name, minute DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "minute": r[1].isoformat(), "total_watts": r[2]}
        for r in rows
    ])


@app.route("/totals/hourly")
def get_hourly_totals():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, hour, SUM(avg_watts)
                FROM wattage_hourly
                GROUP BY system_name, hour
                ORDER BY system_name, hour DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "hour": r[1].isoformat(), "total_watts": r[2]}
        for r in rows
    ])


@app.route("/totals/daily")
def get_daily_totals():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, day, SUM(avg_watts)
                FROM wattage_daily
                GROUP BY system_name, day
                ORDER BY system_name, day DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "day": r[1].isoformat(), "total_watts": r[2]}
        for r in rows
    ])

@app.route("/totals/current_watts")
def get_current_watts():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, SUM(watts)
                FROM (
                    SELECT DISTINCT ON (source, system_name) system_name, watts
                    FROM wattage_readings
                    ORDER BY source, system_name, timestamp DESC
                ) AS latest_readings
                GROUP BY system_name
                ORDER BY system_name;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "current_watts": r[1]}
        for r in rows
    ])


@app.route("/totals/kwh_per_day")
def get_kwh_per_day():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, day, SUM(avg_watts) / 1000.0 * 24.0 AS kwh
                FROM wattage_daily
                GROUP BY system_name, day
                ORDER BY system_name, day DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "day": r[1].isoformat(), "kwh": r[2]}
        for r in rows
    ])


@app.route("/totals/lifetime_kwh")
def get_lifetime_kwh():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, SUM(avg_watts) / 1000.0 * 24.0 AS kwh
                FROM wattage_daily
                GROUP BY system_name
                ORDER BY system_name;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"system_name": r[0], "lifetime_kwh": r[1]}
        for r in rows
    ])

@app.route("/totals/monthly_wh")
def get_monthly_wh():
    # try parsing billing day from env, default to 1 if not set or invalid
    try:
        billing_day = int(os.environ.get("BILLING_DAY", 1))
    except ValueError:
        billing_day = 1
    today = date.today()
    if today.day >= billing_day:
        period_start = today.replace(day=billing_day)
    else:
        first_of_month = today.replace(day=1)
        period_start = (first_of_month - timedelta(days=1)).replace(day=billing_day)

    # get delta in days from period start to today
    delta_days = (today - period_start).days + 1

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT system_name, AVG(day_total_watts) * %s * 24.0 AS wh
                FROM (
                    SELECT system_name, day, SUM(avg_watts) AS day_total_watts
                    FROM wattage_daily
                    WHERE day >= %s AND day <= %s
                    GROUP BY system_name, day
                ) AS daily_totals
                GROUP BY system_name
                ORDER BY system_name;
            """, (delta_days, period_start, today))
            rows = cur.fetchall()
            print(jsonify({
                "period_start": period_start.isoformat(),
                "period_end": today.isoformat(),
                "systems": [
                    {"system_name": r[0], "wh": r[1]}
                    for r in rows
                ],
            }))
            #print json string with indent for readability
            print(json.dumps({
               "period_start": period_start.isoformat(),
               "period_end": today.isoformat(),
               "systems": [
                   {"system_name": r[0], "wh": r[1]}
                   for r in rows
               ],
            }, indent=4))
    return jsonify({
        "period_start": period_start.isoformat(),
        "period_end": today.isoformat(),
        "systems": [
            {"system_name": r[0], "wh": r[1]}
            for r in rows
        ],
    })


def run_api():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
