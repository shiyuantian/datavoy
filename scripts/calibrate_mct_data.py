"""
Calibrate MCT holiday data by computing daily year-over-year growth rates.

When a holiday's total duration differs from the previous year, a simple total
 YoY is not comparable. This script calculates a daily-average YoY as a proxy.

Updates: data/mct_tourism.db
"""

import os
import sqlite3
from typing import Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "mct_tourism.db")

# Mapping for holidays whose name changes year-to-year (e.g. 国庆中秋 vs 国庆)
PREVIOUS_YEAR_HOLIDAY_MAP = {
    "国庆中秋": "国庆",  # 2025 国庆中秋 compares to 2024 国庆
}

MISSING_REASONS = {
    (2026, "元旦", "visitor_yoy"): "2025年元旦仅放假1天（1月1日周三，不调休），文旅部未发布全国单日出游数据",
    (2026, "元旦", "spending_yoy"): "2025年元旦仅放假1天（1月1日周三，不调休），文旅部未发布全国单日出游花费数据",
    (2024, "中秋", "visitor_yoy"): "2023年中秋与国庆合并披露为8天合计数据，无单独中秋口径",
    (2024, "中秋", "spending_yoy"): "2023年中秋与国庆合并披露为8天合计数据，无单独中秋花费口径",
    (2024, "清明", "visitor_yoy"): "2023年清明仅放假1天（4月5日周三，不调休），文旅部未发布全国单日出游数据",
    (2024, "清明", "spending_yoy"): "2023年清明仅放假1天（4月5日周三，不调休），文旅部未发布全国单日出游花费数据",
}

# Holiday actual dates (start, end) by year and holiday name.
# Sources: State Council official holiday arrangements and MCT disclosures.
HOLIDAY_DATES = {
    (2023, "元旦"): ("2022-12-31", "2023-01-02"),
    (2023, "春节"): ("2023-01-21", "2023-01-27"),
    (2023, "清明"): ("2023-04-05", "2023-04-05"),
    (2023, "五一"): ("2023-04-29", "2023-05-03"),
    (2023, "端午"): ("2023-06-22", "2023-06-24"),
    (2023, "国庆中秋"): ("2023-09-29", "2023-10-06"),
    (2024, "元旦"): ("2023-12-30", "2024-01-01"),
    (2024, "春节"): ("2024-02-10", "2024-02-17"),
    (2024, "清明"): ("2024-04-04", "2024-04-06"),
    (2024, "五一"): ("2024-05-01", "2024-05-05"),
    (2024, "端午"): ("2024-06-08", "2024-06-10"),
    (2024, "中秋"): ("2024-09-15", "2024-09-17"),
    (2024, "国庆"): ("2024-10-01", "2024-10-07"),
    (2025, "元旦"): ("2025-01-01", "2025-01-01"),
    (2025, "春节"): ("2025-01-28", "2025-02-04"),
    (2025, "清明"): ("2025-04-04", "2025-04-06"),
    (2025, "五一"): ("2025-05-01", "2025-05-05"),
    (2025, "端午"): ("2025-05-31", "2025-06-02"),
    (2025, "国庆中秋"): ("2025-10-01", "2025-10-08"),
    (2026, "元旦"): ("2026-01-01", "2026-01-03"),
    (2026, "春节"): ("2026-02-15", "2026-02-23"),
    (2026, "清明"): ("2026-04-04", "2026-04-06"),
    (2026, "五一"): ("2026-05-01", "2026-05-05"),
    (2026, "端午"): ("2026-06-19", "2026-06-21"),
}


def get_records(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM mct_holiday_data ORDER BY year DESC, publish_date DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def find_previous_year_record(records, year: int, holiday_name: str):
    target_holiday = PREVIOUS_YEAR_HOLIDAY_MAP.get(holiday_name, holiday_name)
    for r in records:
        if r["year"] == year - 1 and r["holiday_name"] == target_holiday:
            return r
    return None


def calc_daily_yoy(current_val, current_days, prev_val, prev_days) -> Optional[float]:
    if current_val is None or prev_val is None:
        return None
    if not current_days or not prev_days:
        return None
    if prev_val == 0:
        return None
    current_daily = current_val / current_days
    prev_daily = prev_val / prev_days
    return round((current_daily / prev_daily - 1) * 100, 2)


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        records = get_records(conn)
        updates = []

        for r in records:
            visitor_daily_yoy = None
            spending_daily_yoy = None
            reason_v = None
            reason_s = None

            if r["visitor_yoy"] is None:
                prev = find_previous_year_record(records, r["year"], r["holiday_name"])
                if prev:
                    visitor_daily_yoy = calc_daily_yoy(
                        r["visitor_count"], r["holiday_days"],
                        prev["visitor_count"], prev["holiday_days"]
                    )
                if visitor_daily_yoy is None:
                    reason_v = MISSING_REASONS.get(
                        (r["year"], r["holiday_name"], "visitor_yoy"),
                        "前一年同期全国数据未披露，无法计算同比"
                    )

            if r["spending_yoy"] is None:
                prev = find_previous_year_record(records, r["year"], r["holiday_name"])
                if prev:
                    spending_daily_yoy = calc_daily_yoy(
                        r["spending"], r["holiday_days"],
                        prev["spending"], prev["holiday_days"]
                    )
                if spending_daily_yoy is None:
                    reason_s = MISSING_REASONS.get(
                        (r["year"], r["holiday_name"], "spending_yoy"),
                        "前一年同期全国数据未披露，无法计算同比"
                    )

            if visitor_daily_yoy is not None or spending_daily_yoy is not None or reason_v or reason_s:
                updates.append((
                    visitor_daily_yoy,
                    spending_daily_yoy,
                    reason_v,
                    reason_s,
                    r["id"],
                ))
                if visitor_daily_yoy is not None or spending_daily_yoy is not None:
                    print(
                        f"[calibrate] {r['year']} {r['holiday_name']}: "
                        f"visitor_daily_yoy={visitor_daily_yoy}, spending_daily_yoy={spending_daily_yoy} "
                        f"(vs {prev['year']} {prev['holiday_name']}, {r['holiday_days']}d vs {prev['holiday_days']}d)"
                    )
                if reason_v or reason_s:
                    print(
                        f"[calibrate] {r['year']} {r['holiday_name']}: "
                        f"missing_reason_visitor_yoy={reason_v}, missing_reason_spending_yoy={reason_s}"
                    )

        if updates:
            conn.executemany(
                "UPDATE mct_holiday_data SET visitor_daily_yoy=?, spending_daily_yoy=?, "
                "missing_reason_visitor_yoy=?, missing_reason_spending_yoy=? WHERE id=?",
                updates,
            )
            conn.commit()
            print(f"[calibrate] Updated {len(updates)} records")
        else:
            print("[calibrate] No records needed daily YoY calculation")

        # Enrich holiday actual dates
        date_updates = []
        for r in records:
            start, end = HOLIDAY_DATES.get((r["year"], r["holiday_name"]), (None, None))
            if start or end:
                date_updates.append((start, end, r["id"]))
        if date_updates:
            conn.executemany(
                "UPDATE mct_holiday_data SET holiday_start_date=?, holiday_end_date=? WHERE id=?",
                date_updates,
            )
            conn.commit()
            print(f"[calibrate] Enriched {len(date_updates)} records with holiday dates")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
