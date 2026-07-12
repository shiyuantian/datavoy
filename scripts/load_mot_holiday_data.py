#!/usr/bin/env python3
"""
Load MOT holiday summary data into a SQLite database.

Reads: data/mot_holiday_data_raw.json
Writes: data/mot_holiday_data.db (table: mot_holiday_data)
"""

import json
import os
import sqlite3
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_FILE = os.path.join(ROOT_DIR, "data", "mot_holiday_data_raw.json")
DB_FILE = os.path.join(ROOT_DIR, "data", "mot_holiday_data.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mot_holiday_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER,
    holiday_name TEXT,
    holiday_start_date TEXT,
    holiday_end_date TEXT,
    holiday_days INTEGER,
    publish_date TEXT,
    source_url TEXT,
    source_note TEXT,
    total_flow REAL,
    total_flow_unit TEXT,
    total_flow_yoy REAL,
    railway REAL,
    railway_unit TEXT,
    railway_yoy REAL,
    highway REAL,
    highway_unit TEXT,
    highway_yoy REAL,
    waterway REAL,
    waterway_unit TEXT,
    waterway_yoy REAL,
    aviation REAL,
    aviation_unit TEXT,
    aviation_yoy REAL,
    daily_breakdown TEXT,
    created_at TEXT
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO mot_holiday_data (
    year, holiday_name, holiday_start_date, holiday_end_date, holiday_days,
    publish_date, source_url, source_note,
    total_flow, total_flow_unit, total_flow_yoy,
    railway, railway_unit, railway_yoy,
    highway, highway_unit, highway_yoy,
    waterway, waterway_unit, waterway_yoy,
    aviation, aviation_unit, aviation_yoy,
    daily_breakdown, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def init_db(conn: sqlite3.Connection):
    # Recreate table so schema changes (e.g. new columns) are always applied.
    conn.execute("DROP TABLE IF EXISTS mot_holiday_data;")
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def to_wan(value, unit):
    """Normalize a count value to 万人次. Keeps raw value and unit otherwise."""
    if value is None:
        return None, unit
    if unit == "亿人次":
        return round(value * 10000, 1), "万人次"
    return value, unit


def load_data(conn: sqlite3.Connection):
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    # Full refresh: the JSON is the single source of truth.
    conn.execute("DELETE FROM mot_holiday_data;")

    now = datetime.now().isoformat()
    rows = []
    for r in records:
        total_flow, total_flow_unit = to_wan(r.get("total_flow"), r.get("total_flow_unit", "亿人次"))
        railway, railway_unit = to_wan(r.get("railway"), r.get("railway_unit", "万人次"))
        highway, highway_unit = to_wan(r.get("highway"), r.get("highway_unit", "亿人次"))
        waterway, waterway_unit = to_wan(r.get("waterway"), r.get("waterway_unit", "万人次"))
        aviation, aviation_unit = to_wan(r.get("aviation"), r.get("aviation_unit", "万人次"))

        # Normalize daily breakdown counts to 万人次 as well.
        daily_breakdown = r.get("daily_breakdown")
        if daily_breakdown is not None:
            normalized_daily = []
            for day in daily_breakdown:
                norm_day = dict(day)
                for key in ("total_flow", "railway", "highway", "waterway", "aviation"):
                    unit_key = f"{key}_unit"
                    if key in norm_day and unit_key in norm_day:
                        norm_day[key], norm_day[unit_key] = to_wan(norm_day[key], norm_day[unit_key])
                normalized_daily.append(norm_day)
            daily_breakdown = normalized_daily

        rows.append((
            r.get("year"),
            r.get("holiday_name"),
            r.get("holiday_start_date"),
            r.get("holiday_end_date"),
            r.get("holiday_days"),
            r.get("publish_date"),
            r.get("source_url"),
            r.get("source_note", ""),
            total_flow,
            total_flow_unit,
            r.get("total_flow_yoy"),
            railway,
            railway_unit,
            r.get("railway_yoy"),
            highway,
            highway_unit,
            r.get("highway_yoy"),
            waterway,
            waterway_unit,
            r.get("waterway_yoy"),
            aviation,
            aviation_unit,
            r.get("aviation_yoy"),
            json.dumps(daily_breakdown, ensure_ascii=False) if daily_breakdown is not None else None,
            now,
        ))

    conn.executemany(INSERT_SQL, rows)
    conn.commit()
    return len(rows)


def main():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        init_db(conn)
        count = load_data(conn)
        print(f"[loader] Loaded {count} records into {DB_FILE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
