#!/usr/bin/env python3
"""
Load scraped MOT Spring Festival travel data into a SQLite database.

Reads: data/mot_chunyun_2025_raw.json
Writes: data/mot_chunyun.db (table: mot_chunyun_data)
"""

import json
import os
import sqlite3
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_FILE = os.path.join(ROOT_DIR, "data", "mot_chunyun_2025_raw.json")
DB_FILE = os.path.join(ROOT_DIR, "data", "mot_chunyun.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mot_chunyun_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    publish_date TEXT,
    chunyun_day INTEGER,
    title TEXT,
    source_url TEXT UNIQUE,
    total_flow REAL,
    total_flow_yoy REAL,
    railway REAL,
    railway_yoy REAL,
    highway REAL,
    highway_yoy REAL,
    waterway REAL,
    waterway_yoy REAL,
    aviation REAL,
    aviation_yoy REAL,
    raw_text TEXT,
    created_at TEXT
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO mot_chunyun_data (
    date, publish_date, chunyun_day, title, source_url,
    total_flow, total_flow_yoy,
    railway, railway_yoy,
    highway, highway_yoy,
    waterway, waterway_yoy,
    aviation, aviation_yoy,
    raw_text, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def init_db(conn: sqlite3.Connection):
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def load_data(conn: sqlite3.Connection):
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    now = datetime.now().isoformat()
    rows = []
    for r in records:
        rows.append((
            r.get("date"),
            r.get("publish_date"),
            r.get("chunyun_day"),
            r.get("title"),
            r.get("source_url"),
            r.get("total_flow"),
            r.get("total_flow_yoy"),
            r.get("railway"),
            r.get("railway_yoy"),
            r.get("highway"),
            r.get("highway_yoy"),
            r.get("waterway"),
            r.get("waterway_yoy"),
            r.get("aviation"),
            r.get("aviation_yoy"),
            r.get("raw_text", ""),
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
