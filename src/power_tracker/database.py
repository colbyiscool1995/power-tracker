import os
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as Connection
from dotenv import load_dotenv

load_dotenv()

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


def get_connection() -> Connection:
    """Return a PostgreSQL connection using environment variables.

    Required env vars:
        DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    """
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def init_db():
    _run_migrations()
    _flush_residual_readings()


def _run_migrations():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        conn.commit()

        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        for path in migration_files:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE filename = %s;",
                    (path.name,),
                )
                if cur.fetchone():
                    continue

            print(f"Applying migration: {path.name}")
            with conn.cursor() as cur:
                cur.execute(path.read_text())
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s);",
                    (path.name,),
                )
            conn.commit()


def _flush_residual_readings():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM wattage_readings;")
            count = cur.fetchone()[0]
            if count > 0:
                print(f"Found {count} residual readings from previous run — rolling up.")
                cur.execute("""
                    INSERT INTO wattage_averages (source, avg_watts, minute)
                    SELECT source, AVG(watts), date_trunc('minute', MIN(timestamp))
                    FROM wattage_readings
                    GROUP BY source;
                """)
                cur.execute("DELETE FROM wattage_readings;")
        conn.commit()


def rollup_minute_averages():
    """Compute per-source averages from wattage_readings, store in wattage_averages, then delete raw rows."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wattage_averages (source, avg_watts, system_name, local_ip, minute)
                SELECT source, AVG(watts), system_name, local_ip, date_trunc('minute', NOW())
                FROM wattage_readings
                GROUP BY source, system_name, local_ip;
            """)
            cur.execute("""
                DELETE FROM wattage_readings
                WHERE timestamp >= date_trunc('minute', NOW()) - INTERVAL '1 minute'
                  AND timestamp <  date_trunc('minute', NOW());
            """)
        conn.commit()


def rollup_hourly_averages():
    """Compute per-source hourly averages from wattage_averages and upsert into wattage_hourly."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wattage_hourly (source, avg_watts, system_name, local_ip, hour)
                SELECT source, AVG(avg_watts), system_name, local_ip, date_trunc('hour', NOW()) - INTERVAL '1 hour'
                FROM wattage_averages
                WHERE minute >= date_trunc('hour', NOW()) - INTERVAL '1 hour'
                  AND minute <  date_trunc('hour', NOW())
                GROUP BY source, system_name, local_ip
                ON CONFLICT (source, hour)
                DO UPDATE SET avg_watts = EXCLUDED.avg_watts;
            """)
        conn.commit()


def rollup_daily_averages():
    """Compute per-source daily averages from wattage_hourly, store in wattage_daily, delete rolled-up rows."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wattage_daily (source, avg_watts, system_name, local_ip, day)
                SELECT source, AVG(avg_watts), system_name, local_ip, (date_trunc('day', NOW()) - INTERVAL '1 day')::DATE
                FROM wattage_hourly
                WHERE hour >= date_trunc('day', NOW()) - INTERVAL '1 day'
                  AND hour <  date_trunc('day', NOW())
                GROUP BY source, system_name, local_ip;
            """)
        conn.commit()


def insert_wattage_reading(source: str, watts: float, system_name: str = "", local_ip: str = ""):
    """Insert a wattage reading into the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wattage_readings (source, watts, system_name, local_ip)
                VALUES (%s, %s, %s, %s);
            """, (source, watts, system_name, local_ip))
        conn.commit()
