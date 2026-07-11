#!/usr/bin/env python3
"""
Build the combined tourism + transport data dashboard.

Usage:
    python build_site.py

Reads:
    - data/mct_tourism.db (table: mct_holiday_data)
    - data/mot_holiday_data.db (table: mot_holiday_data)
Writes: index.html
"""

import json
import os
import sqlite3

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MCT_DB = os.path.join(ROOT_DIR, "data", "mct_tourism.db")
MOT_DB = os.path.join(ROOT_DIR, "data", "mot_holiday_data.db")
NIA_DB = os.path.join(ROOT_DIR, "data", "nia_entry_exit.db")
OUT_PATH = os.path.join(ROOT_DIR, "index.html")
TEMPLATE_PATH = os.path.join(ROOT_DIR, "templates", "index_template.html")


def load_template():
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def read_mct():
    conn = sqlite3.connect(MCT_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM mct_holiday_data ORDER BY year DESC, publish_date DESC").fetchall()
    records = [dict(r) for r in rows]
    conn.close()
    return records


def read_mot():
    conn = sqlite3.connect(MOT_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM mot_holiday_data ORDER BY year DESC, holiday_start_date DESC").fetchall()
    records = []
    for r in rows:
        rec = dict(r)
        if rec.get("daily_breakdown"):
            rec["daily_breakdown"] = json.loads(rec["daily_breakdown"])
        records.append(rec)
    conn.close()
    return records


def read_nia():
    if not os.path.exists(NIA_DB):
        return []
    conn = sqlite3.connect(NIA_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM nia_data ORDER BY year DESC, period_order, publish_date"
    ).fetchall()
    records = [dict(r) for r in rows]
    conn.close()
    return records


def main():
    mct_records = read_mct()
    mot_records = read_mot()
    nia_records = read_nia()
    template = load_template()
    rendered = (
        template
        .replace("{mct_data_json}", json.dumps(mct_records, ensure_ascii=False))
        .replace("{mot_data_json}", json.dumps(mot_records, ensure_ascii=False))
        .replace("{nia_data_json}", json.dumps(nia_records, ensure_ascii=False))
    )
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"Generated {OUT_PATH} (MCT: {len(mct_records)}, MOT: {len(mot_records)}, NIA: {len(nia_records)})")


if __name__ == "__main__":
    main()
