CREATE TABLE IF NOT EXISTS wattage_readings (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    watts REAL NOT NULL,
    system_name TEXT NOT NULL DEFAULT '',
    local_ip TEXT NOT NULL DEFAULT '',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wattage_averages (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    avg_watts REAL NOT NULL,
    system_name TEXT NOT NULL DEFAULT '',
    local_ip TEXT NOT NULL DEFAULT '',
    minute TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS wattage_hourly (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    avg_watts REAL NOT NULL,
    system_name TEXT NOT NULL DEFAULT '',
    local_ip TEXT NOT NULL DEFAULT '',
    hour TIMESTAMPTZ NOT NULL
);

DELETE FROM wattage_hourly a
USING wattage_hourly b
WHERE a.id < b.id
  AND a.source = b.source
  AND a.hour = b.hour;

CREATE UNIQUE INDEX IF NOT EXISTS idx_wattage_hourly_source_hour
ON wattage_hourly (source, hour);

CREATE TABLE IF NOT EXISTS wattage_daily (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    avg_watts REAL NOT NULL,
    system_name TEXT NOT NULL DEFAULT '',
    local_ip TEXT NOT NULL DEFAULT '',
    day DATE NOT NULL
);
