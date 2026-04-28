import logging
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

_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(message)s"
_log_file_path: str | None = None
_log_lock = threading.Lock()

log = logging.getLogger("power_tracker")


def _setup_logging(log_path: str) -> None:
    global _log_file_path
    _log_file_path = log_path
    fh = logging.FileHandler(log_path)
    fh.setFormatter(logging.Formatter(_LOG_FORMAT))
    logging.root.addHandler(fh)
    log.info("Logging to %s", log_path)


def _truncate_log() -> None:
    if _log_file_path is None:
        return
    with _log_lock:
        root = logging.root
        old = [h for h in root.handlers
               if isinstance(h, logging.FileHandler)
               and h.baseFilename == os.path.abspath(_log_file_path)]
        for h in old:
            h.close()
            root.removeHandler(h)
        open(_log_file_path, "w").close()
        fh = logging.FileHandler(_log_file_path)
        fh.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(fh)
    log.info("Log truncated at top of hour")


def _build_poll_loop():
    sensor = get_sensor()
    system_name = get_system_name()
    local_ip = get_local_ip()
    log.info("System: %s (%s)", system_name, local_ip)

    def _poll_loop():
        while True:
            wattage = sensor.get_wattage()
            for source, watts in wattage.items():
                log.info("%s: %.3f W", source, watts)
                insert_wattage_reading(source, watts, system_name, local_ip)
            time.sleep(5)
    return _poll_loop


def _minute_checker():
    while True:
        now = time.localtime()
        if now.tm_sec == 0:
            log.info("--- top of minute: %s ---", time.strftime("%H:%M", now))
            rollup_minute_averages()
            time.sleep(1)
        else:
            time.sleep(0.5)


def _hour_checker():
    while True:
        now = time.localtime()
        if now.tm_min == 0 and now.tm_sec == 0:
            log.info("--- top of hour: %s ---", time.strftime("%H:00", now))
            _truncate_log()
            try:
                rollup_hourly_averages()
            except Exception as e:
                log.error("Hourly rollup failed: %s", e)
            else:
                if now.tm_hour == 0:
                    log.info("--- midnight rollup: %s ---", time.strftime("%Y-%m-%d", now))
                    try:
                        rollup_daily_averages()
                    except Exception as e:
                        log.error("Daily rollup failed: %s", e)
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
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    if mode == "server":
        log_path = os.environ.get("LOG_FILE", "/var/log/power_tracker.log")
        _setup_logging(log_path)
    log.info("Starting in %s mode.", mode)
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
