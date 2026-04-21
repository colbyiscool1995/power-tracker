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
            cur.execute("SELECT SUM(watts) FROM wattage_readings;")
            total = cur.fetchone()[0]
    return jsonify({"total_watts": total or 0.0})


@app.route("/totals/minute")
def get_minute_totals():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT minute, SUM(avg_watts)
                FROM wattage_averages
                GROUP BY minute
                ORDER BY minute DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"minute": r[0].isoformat(), "total_watts": r[1]}
        for r in rows
    ])


@app.route("/totals/hourly")
def get_hourly_totals():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT hour, SUM(avg_watts)
                FROM wattage_hourly
                GROUP BY hour
                ORDER BY hour DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"hour": r[0].isoformat(), "total_watts": r[1]}
        for r in rows
    ])


@app.route("/totals/daily")
def get_daily_totals():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT day, SUM(avg_watts)
                FROM wattage_daily
                GROUP BY day
                ORDER BY day DESC
                LIMIT 100;
            """)
            rows = cur.fetchall()
    return jsonify([
        {"day": r[0].isoformat(), "total_watts": r[1]}
        for r in rows
    ])


def run_api():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
