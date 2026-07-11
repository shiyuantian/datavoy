#!/usr/bin/env python3
"""Scrape NIA (国家移民管理局) entry-exit statistics and store in SQLite."""
import gzip
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
import lxml.html

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "nia_entry_exit.db"

LIST_URL = "https://www.nia.gov.cn/n741440/n741567/index{_page}.html"
CONTENT_BASE = "https://www.nia.gov.cn/n741440/n741567/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

PERIOD_KEYWORDS = {
    "元旦": "元旦",
    "春节": "春节",
    "清明": "清明",
    "五一": "五一",
    "端午": "端午",
    "国庆中秋": "国庆中秋",
    "中秋节": "中秋",
    "国庆节": "国庆",
    "全年": "全年",
    "上半年": "上半年",
    "下半年": "下半年",
    "一季度": "一季度",
    "二季度": "二季度",
    "三季度": "三季度",
    "四季度": "四季度",
    "1至8月": "1-8月",
    "1-8月": "1-8月",
}

PERIOD_ORDER = {
    "全年": 1,
    "上半年": 2,
    "下半年": 3,
    "一季度": 4,
    "二季度": 5,
    "三季度": 6,
    "四季度": 7,
    "元旦": 8,
    "春节": 9,
    "清明": 10,
    "五一": 11,
    "端午": 12,
    "国庆中秋": 13,
    "1-8月": 14,
}


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nia_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            period_name TEXT NOT NULL,
            period_order INTEGER NOT NULL DEFAULT 99,
            publish_date TEXT,
            source_url TEXT NOT NULL,
            title TEXT,
            total_count REAL,
            total_unit TEXT,
            total_yoy REAL,
            mainland_count REAL,
            mainland_unit TEXT,
            mainland_yoy REAL,
            hk_tw_mo_count REAL,
            hk_tw_mo_unit TEXT,
            hk_tw_mo_yoy REAL,
            foreign_count REAL,
            foreign_unit TEXT,
            foreign_yoy REAL,
            visa_free_count REAL,
            visa_free_unit TEXT,
            visa_free_yoy REAL,
            raw_text TEXT,
            updated_at TEXT,
            UNIQUE(year, period_name)
        )
        """
    )
    conn.commit()
    return conn


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    return data


def list_links(page_index=0):
    """Return list of (url, title) for relevant articles on a list page."""
    if page_index == 0:
        url = "https://www.nia.gov.cn/n741440/n741567/index.html"
    else:
        url = f"https://www.nia.gov.cn/n741440/n741567/index_753309_{page_index}.html"
    html_bytes = fetch(url)
    html = html_bytes.decode("utf-8", errors="ignore")
    tree = lxml.html.fromstring(html)
    items = []
    for a in tree.xpath("//a[contains(@href, '/content.html')]"):
        href = a.get("href")
        title = (a.text_content() or "").strip()
        if not href or not title:
            continue
        if not any(kw in title for kw in PERIOD_KEYWORDS):
            continue
        # skip "一图读懂" info-graphics
        if "一图" in title or "图解" in title:
            continue
        abs_url = urllib.parse.urljoin(url, href)
        items.append((abs_url, title))
    return items


def parse_article(html_bytes):
    tree = lxml.html.fromstring(html_bytes)
    title_metas = tree.xpath('//meta[@name="ArticleTitle"]/@content')
    title = title_metas[0] if title_metas else ""
    pub_dates = tree.xpath('//meta[@name="PubDate"]/@content')
    publish_date = pub_dates[0][:10] if pub_dates else ""
    content = tree.xpath('//div[@class="content"]//p[not(contains(@class,"sv_texth1"))]//text()')
    text = "".join(t.strip() for t in content if t.strip())
    return title, publish_date, text


def signed_yoy(segment):
    """Extract a YoY change from a short segment and apply sign.

    Handles:
      - 增长/上升/下降 12.9%
      - 增长 2.8倍  -> returned as 280.0
    """
    if not segment:
        return None
    m = re.search(r"(?:较[^，。；,]*?|同比)(?:增长|上升|下降)([\d.]+)%", segment)
    if m:
        val = float(m.group(1))
        if "下降" in segment:
            val = -val
        return val
    # e.g. 增长2.8倍 -> 280%
    m = re.search(r"(?:较[^，。；,]*?|同比)(?:增长|上升|下降)([\d.]+)倍", segment)
    if m:
        val = float(m.group(1)) * 100
        if "下降" in segment:
            val = -val
        return val
    return None


def extract_pair(pattern, text, stop_keywords=None):
    """Find the first occurrence of `pattern` and capture the next YoY before any stop keyword."""
    if stop_keywords:
        stop = "|".join(re.escape(k) for k in stop_keywords)
        regex = f"{pattern}(?:(?!{stop}).)*?(?:增长|上升|下降)([\\d.]+)(?:%|倍)"
    else:
        regex = f"{pattern}(?:增长|上升|下降)([\\d.]+)(?:%|倍)"
    m = re.search(regex, text, re.DOTALL)
    if not m:
        # fall back to count only
        m2 = re.search(pattern, text)
        if m2:
            return float(m2.group(1)), m2.group(2), None
        return None, None, None
    count = float(m.group(1))
    unit = m.group(2)
    segment = m.group(0)
    yoy = signed_yoy(segment)
    return count, unit, yoy


def extract_metrics(text):
    metrics = {}
    t = text

    # --- total ---
    total_count, total_unit, total_yoy = None, None, None
    total_patterns = [
        r"(?:超)?([\d.]+)(万|亿)人次中外人员出入境",
        r"查验出入境人员(?:超)?([\d.]+)(万|亿)人次",
        r"累计查验出入境人员(?:超)?([\d.]+)(万|亿)人次",
        r"出入境人员(?:达|共|累计|超)?([\d.]+)(万|亿)人次",
    ]
    for pat in total_patterns:
        count, unit, yoy = extract_pair(pat, t, stop_keywords=["其中", "内地居民", "港澳台居民", "外国人", "适用免签", "免签入境"])
        if count is not None:
            total_count, total_unit, total_yoy = count, unit, yoy
            break
    if total_count is not None:
        metrics["total_count"] = total_count
        metrics["total_unit"] = total_unit
        metrics["total_yoy"] = total_yoy

    # --- combined patterns (annual / half-year / quarter style) ---
    combined3 = re.search(
        r"内地(?:（大陆）)?居民([\d.]+)(万|亿)人次[、，]港澳台居民([\d.]+)(万|亿)人次[、，](?:外国人|外籍人员)([\d.]+)(万|亿)人次[，,]同比分别(?:增长|上升|下降)([\d.]+)%[、，]([\d.]+)%[、，]([\d.]+)%",
        t,
    )
    combined2 = re.search(
        r"内地(?:（大陆）)?居民([\d.]+)(万|亿)人次[、，]港澳台居民([\d.]+)(万|亿)人次[，,]同比分别(?:增长|上升|下降)([\d.]+)%[、，]([\d.]+)%",
        t,
    )
    if combined3:
        metrics["mainland_count"] = float(combined3.group(1))
        metrics["mainland_unit"] = combined3.group(2)
        metrics["mainland_yoy"] = float(combined3.group(7))
        metrics["hk_tw_mo_count"] = float(combined3.group(3))
        metrics["hk_tw_mo_unit"] = combined3.group(4)
        metrics["hk_tw_mo_yoy"] = float(combined3.group(8))
        metrics["foreign_count"] = float(combined3.group(5))
        metrics["foreign_unit"] = combined3.group(6)
        metrics["foreign_yoy"] = float(combined3.group(9))
    elif combined2:
        metrics["mainland_count"] = float(combined2.group(1))
        metrics["mainland_unit"] = combined2.group(2)
        metrics["mainland_yoy"] = float(combined2.group(5))
        metrics["hk_tw_mo_count"] = float(combined2.group(3))
        metrics["hk_tw_mo_unit"] = combined2.group(4)
        metrics["hk_tw_mo_yoy"] = float(combined2.group(6))

    # --- individual category patterns ---
    if "mainland_count" not in metrics:
        c, u, y = extract_pair(
            r"内地(?:（大陆）)?居民(?:出入境)?([\d.]+)(万|亿)人次",
            t,
            stop_keywords=["港澳台居民", "外国人", "适用免签", "免签入境"],
        )
        if c is not None:
            metrics["mainland_count"] = c
            metrics["mainland_unit"] = u
            metrics["mainland_yoy"] = y

    if "hk_tw_mo_count" not in metrics:
        c, u, y = extract_pair(
            r"港澳台居民(?:出入境)?([\d.]+)(万|亿)人次",
            t,
            stop_keywords=["外国人", "适用免签", "免签入境", "内地居民"],
        )
        if c is not None:
            metrics["hk_tw_mo_count"] = c
            metrics["hk_tw_mo_unit"] = u
            metrics["hk_tw_mo_yoy"] = y

    if "foreign_count" not in metrics:
        c, u, y = extract_pair(
            r"外国人(?:入出境|出入境)?([\d.]+)(万|亿)人次",
            t,
            stop_keywords=["适用免签", "免签入境", "内地居民", "港澳台居民"],
        )
        if c is not None:
            metrics["foreign_count"] = c
            metrics["foreign_unit"] = u
            metrics["foreign_yoy"] = y

    # --- visa-free ---
    c, u, y = extract_pair(
        r"适用免签政策入境([\d.]+)(万|亿)人次",
        t,
        stop_keywords=["内地居民", "港澳台居民"],
    )
    if c is None:
        c, u, y = extract_pair(
            r"免签入境外国人([\d.]+)(万|亿)人次",
            t,
            stop_keywords=["内地居民", "港澳台居民"],
        )
    if c is not None:
        metrics["visa_free_count"] = c
        metrics["visa_free_unit"] = u
        metrics["visa_free_yoy"] = y

    return metrics


def determine_period(title, text):
    combined = title + text
    for kw, period in PERIOD_KEYWORDS.items():
        if kw in combined:
            return period
    # Annual summaries often titled like "2024年6.1亿人次出入境"
    if re.search(r"20\d{2}年.*出入境", title) and "上半年" not in title and "下半年" not in title:
        return "全年"
    return None


def determine_year(title, text, publish_date):
    # Look for a 4-digit year in title/text that is likely the data year
    years = re.findall(r"20\d{2}", title + text)
    if years:
        # Prefer the first year mentioned in title, or the smallest year if multiple
        # For holiday articles, the data year is usually the first year in title.
        return int(years[0])
    if publish_date:
        return int(publish_date[:4])
    return None


def save_record(conn, url, title, publish_date, text, metrics):
    period = determine_period(title, text)
    if not period:
        return False
    year = determine_year(title, text, publish_date)
    if not year or year < 2023:
        return False
    if metrics.get("total_count") is None:
        return False

    period_order = PERIOD_ORDER.get(period, 99)
    now = datetime.now().isoformat()

    conn.execute(
        """
        INSERT INTO nia_data (
            year, period_name, period_order, publish_date, source_url, title,
            total_count, total_unit, total_yoy,
            mainland_count, mainland_unit, mainland_yoy,
            hk_tw_mo_count, hk_tw_mo_unit, hk_tw_mo_yoy,
            foreign_count, foreign_unit, foreign_yoy,
            visa_free_count, visa_free_unit, visa_free_yoy,
            raw_text, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(year, period_name) DO UPDATE SET
            period_order=excluded.period_order,
            publish_date=excluded.publish_date,
            source_url=excluded.source_url,
            title=excluded.title,
            total_count=excluded.total_count,
            total_unit=excluded.total_unit,
            total_yoy=excluded.total_yoy,
            mainland_count=excluded.mainland_count,
            mainland_unit=excluded.mainland_unit,
            mainland_yoy=excluded.mainland_yoy,
            hk_tw_mo_count=excluded.hk_tw_mo_count,
            hk_tw_mo_unit=excluded.hk_tw_mo_unit,
            hk_tw_mo_yoy=excluded.hk_tw_mo_yoy,
            foreign_count=excluded.foreign_count,
            foreign_unit=excluded.foreign_unit,
            foreign_yoy=excluded.foreign_yoy,
            visa_free_count=excluded.visa_free_count,
            visa_free_unit=excluded.visa_free_unit,
            visa_free_yoy=excluded.visa_free_yoy,
            raw_text=excluded.raw_text,
            updated_at=excluded.updated_at
        """,
        (
            year,
            period,
            period_order,
            publish_date,
            url,
            title,
            metrics.get("total_count"),
            metrics.get("total_unit"),
            metrics.get("total_yoy"),
            metrics.get("mainland_count"),
            metrics.get("mainland_unit"),
            metrics.get("mainland_yoy"),
            metrics.get("hk_tw_mo_count"),
            metrics.get("hk_tw_mo_unit"),
            metrics.get("hk_tw_mo_yoy"),
            metrics.get("foreign_count"),
            metrics.get("foreign_unit"),
            metrics.get("foreign_yoy"),
            metrics.get("visa_free_count"),
            metrics.get("visa_free_unit"),
            metrics.get("visa_free_yoy"),
            text,
            now,
        ),
    )
    conn.commit()
    return True


def scrape(max_pages=15):
    conn = init_db()
    seen = set()
    for page in range(max_pages + 1):
        try:
            links = list_links(page)
        except Exception as e:
            print(f"Page {page} error: {e}")
            break
        if not links:
            break
        for url, title in links:
            if url in seen:
                continue
            seen.add(url)
            print(f"Fetching {title} -> {url}")
            try:
                html = fetch(url)
                article_title, pub_date, text = parse_article(html)
                metrics = extract_metrics(text)
                saved = save_record(conn, url, article_title or title, pub_date, text, metrics)
                print("  saved" if saved else "  skipped", metrics)
            except Exception as e:
                print(f"  error: {e}")
            time.sleep(0.5)
    conn.close()


if __name__ == "__main__":
    scrape()
