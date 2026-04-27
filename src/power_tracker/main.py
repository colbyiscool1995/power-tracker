import os
import threading
import time

from dotenv import load_dotenv

from power_tracker.api import run_api
from power_tracker.consumer import run_consumer
from power_tracker.database import init_db, insert_wattage_reading, rollup_minute_averages, rollup_hourly_averages, rollup_daily_averages
from power_tracker.sensors import get_sensor
from power_tracker.system_info import get_local_ip, get_system_name

load_dotenv()


def _build_poll_loop():
    sensor = get_sensor()
    system_name = get_system_name()
    local_ip = get_local_ip()
    print(f"System: {system_name} ({local_ip})")

    def _poll_loop():
        while True:
            wattage = sensor.get_wattage()
            for source, watts in wattage.items():
                print(f"{source}: {watts:.3f} W")
                insert_wattage_reading(source, watts, system_name, local_ip)
            time.sleep(5)
    return _poll_loop


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


_SHARED_THREADS = [
    ("minute",   _minute_checker),
    ("hour",     _hour_checker),
    ("api",      run_api),
]


def main():
    mode = os.environ.get("RUN_MODE", "standalone").lower()
    print(f"Starting in {mode} mode.")
    init_db()

    if mode == "standalone":
        ingest = ("poll", _build_poll_loop())
    elif mode == "server":
        ingest = ("consumer", run_consumer)
    else:
        raise RuntimeError(f"Unknown RUN_MODE '{mode}'. Use 'standalone' or 'server'.")

    threads = [
        threading.Thread(name=name, target=fn, daemon=True)
        for name, fn in [ingest, *_SHARED_THREADS]
    ]
    for t in threads:
        t.start()
    threads[0].join()


if __name__ == "__main__":
    main()
