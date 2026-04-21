import json
import subprocess
import threading
import time

from power_tracker.api import run_api
from power_tracker.database import init_db, insert_wattage_reading, rollup_minute_averages, rollup_hourly_averages, rollup_daily_averages


def get_wattage() -> dict[str, float]:
    """Returns all wattage readings from lm-sensors.

    Returns dict mapping '{chip}/{label}' -> watts (float).
    Raises RuntimeError if sensors binary not found or returns error.
    """
    result = subprocess.run(
        ["sensors", "-j"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sensors failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    readings: dict[str, float] = {}

    for chip, chip_data in data.items():
        if not isinstance(chip_data, dict):
            continue
        for label, sensor_data in chip_data.items():
            if label == "Adapter" or not isinstance(sensor_data, dict):
                continue
            for key, value in sensor_data.items():
                if key.startswith("power") and (
                    key.endswith("_input") or key.endswith("_average")
                ):
                    readings[f"{chip}/{label}"] = float(value)

    return readings


def _poll_loop():
    while True:
        wattage = get_wattage()
        for source, watts in wattage.items():
            print(f"{source}: {watts:.3f} W")
            insert_wattage_reading(source, watts)
        time.sleep(5)


def _minute_checker():
    while True:
        now = time.localtime()
        if now.tm_sec == 0:
            print(f"--- top of minute: {time.strftime('%H:%M', now)} ---")
            rollup_minute_averages()
            time.sleep(1)
        else:
            time.sleep(0.5)


def _hour_checker():
    while True:
        now = time.localtime()
        if now.tm_min == 0 and now.tm_sec == 0:
            print(f"--- top of hour: {time.strftime('%H:00', now)} ---")
            try:
                rollup_hourly_averages()
            except Exception as e:
                print(f"Hourly rollup failed: {e}")
            else:
                if now.tm_hour == 0:
                    print(f"--- midnight rollup: {time.strftime('%Y-%m-%d', now)} ---")
                    try:
                        rollup_daily_averages()
                    except Exception as e:
                        print(f"Daily rollup failed: {e}")
            time.sleep(1)
        else:
            time.sleep(0.5)


_THREADS = [
    ("poll",    _poll_loop),
    ("minute",  _minute_checker),
    ("hour",    _hour_checker),
    ("api",     run_api),
]


def main():
    init_db()
    threads = [
        threading.Thread(name=name, target=fn, daemon=True)
        for name, fn in _THREADS
    ]
    for t in threads:
        t.start()
    threads[0].join()


if __name__ == "__main__":
    main()
