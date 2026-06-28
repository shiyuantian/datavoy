"""
Load scraped MCT tourism data into a SQLite database.

Reads: data/mct_tourism_raw.json
Writes: data/mct_tourism.db (table: mct_holiday_data)
"""

import json
import os
import sqlite3
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_FILE = os.path.join(ROOT_DIR, "data", "mct_holiday_data_raw.json")
DB_FILE = os.path.join(ROOT_DIR, "data", "mct_tourism.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mct_holiday_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER,
    holiday_name TEXT,
    publish_date TEXT,
    title TEXT,
    source_url TEXT UNIQUE,
    visitor_count REAL,
    visitor_yoy REAL,
    visitor_yoy_2019 REAL,
    spending REAL,
    spending_yoy REAL,
    spending_yoy_2019 REAL,
    holiday_days INTEGER,
    holiday_start_date TEXT,
    holiday_end_date TEXT,
    visitor_daily_yoy REAL,
    spending_daily_yoy REAL,
    missing_reason_visitor_yoy TEXT,
    missing_reason_spending_yoy TEXT,
    raw_text TEXT,
    created_at TEXT
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO mct_holiday_data (
    year, holiday_name, publish_date, title, source_url,
    visitor_count, visitor_yoy, visitor_yoy_2019,
    spending, spending_yoy, spending_yoy_2019,
    holiday_days, holiday_start_date, holiday_end_date, raw_text, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            r.get("year"),
            r.get("holiday_name"),
            r.get("publish_date"),
            r.get("title"),
            r.get("source_url"),
            r.get("visitor_count"),
            r.get("visitor_yoy"),
            r.get("visitor_yoy_2019"),
            r.get("spending"),
            r.get("spending_yoy"),
            r.get("spending_yoy_2019"),
            r.get("holiday_days"),
            None,
            None,
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
