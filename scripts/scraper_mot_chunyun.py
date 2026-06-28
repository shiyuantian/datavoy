#!/usr/bin/env python3
"""
Scraper for Ministry of Transport (MOT) Spring Festival travel data.

Crawls the 2025 Spring Festival travel data column and extracts daily
inter-regional passenger flow by mode (railway, highway, waterway, aviation).

Source: https://www.mot.gov.cn/zhuanti/2025chunyun/chunyunshuju/
"""

import html as html_module
import json
import os
import re
import time
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(ROOT_DIR, "data", "mot_chunyun_2025_raw.json")

BASE_URL = "https://www.mot.gov.cn/zhuanti/2025chunyun/chunyunshuju/"
LIST_PAGES = ["index.html"] + [f"index_{i}.html" for i in range(1, 4)]
REQUEST_DELAY = 0.5


def fetch(url: str) -> str:
    """Fetch URL and return UTF-8 text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gbk", errors="ignore")


class ListPageParser(HTMLParser):
    """Parse list page to extract article links and titles."""

    def __init__(self):
        super().__init__()
        self.in_target_a = False
        self.current_href = None
        self.current_title = None
        self.current_date = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            title = attrs_dict.get("title", "")
            # Only data articles contain "全社会跨区域人员流动量"
            if href.startswith("./20") and "全社会跨区域人员流动量" in title:
                self.in_target_a = True
                self.current_href = href
                self.current_title = title

    def handle_data(self, data):
        if self.in_target_a:
            # Try to extract publish date from text like "02月22日"
            m = re.search(r'(\d{2})月(\d{2})日', data)
            if m:
                self.current_date = f"2025-{m.group(1)}-{m.group(2)}"

    def handle_endtag(self, tag):
        if tag == "a" and self.in_target_a:
            if self.current_href and self.current_title:
                self.items.append({
                    "href": self.current_href,
                    "title": self.current_title,
                    "publish_date": self.current_date,
                })
            self.in_target_a = False
            self.current_href = None
            self.current_title = None
            self.current_date = None


def extract_zoom_text(html: str) -> str:
    """Extract main article text from the id=Zoom container."""
    start = html.find('id="Zoom"')
    if start == -1:
        return html
    # Find opening <div ... id="Zoom">
    tag_start = html.rfind('<', 0, start)
    content_start = html.find('>', start) + 1
    if content_start <= 0:
        return html
    # Balance nested divs
    depth = 0
    i = content_start
    while i < len(html):
        if html[i:i+4].lower() == '<div':
            depth += 1
            i += 4
        elif html[i:i+6].lower() == '</div>':
            if depth == 0:
                content = html[content_start:i]
                break
            depth -= 1
            i += 6
        else:
            i += 1
    else:
        content = html[content_start:]

    text = re.sub(r'<[^>]+>', ' ', content)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_article(html: str, source_url: str, publish_date: str) -> dict:
    """Parse a single MOT article and extract metrics."""
    title_match = re.search(r'<title>(.*?)</title>', html, re.S)
    title = title_match.group(1).strip() if title_match else ""

    text = extract_zoom_text(html)

    record = {
        "source_url": source_url,
        "publish_date": publish_date,
        "title": title,
        "raw_text": text[:1500],
    }

    # Date and Chunyun day, e.g. "2025年2月21日（春运第39天，农历正月二十四，星期五）"
    date_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*（春运第(\d+)天'
    dm = re.search(date_pattern, text)
    if dm:
        record["date"] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        record["chunyun_day"] = int(dm.group(4))
    else:
        # Some articles omit the year, e.g. "1月14日（春运第1天...". Infer year from context.
        dm2 = re.search(r'(\d{1,2})月(\d{1,2})日\s*（春运第(\d+)天', text)
        if dm2:
            year = 2025
            # If the article explicitly references the previous year's data, use that year
            if re.search(r'来自2024年|2024年春运|2024年同期', text[:200]):
                year = 2024
            record["date"] = f"{year}-{int(dm2.group(1)):02d}-{int(dm2.group(2)):02d}"
            record["chunyun_day"] = int(dm2.group(3))
        else:
            tm = re.search(r'(\d{1,2})月(\d{1,2})日', title)
            if tm:
                record["date"] = f"2025-{int(tm.group(1)):02d}-{int(tm.group(2)):02d}"
            else:
                record["date"] = None
            record["chunyun_day"] = None

    # Split text into sentences/clauses for clause-level parsing
    clauses = re.split(r'[。；!！?？]', text)

    def find_clause(prefixes):
        for c in clauses:
            for p in prefixes:
                if p in c:
                    return c
        return None

    def extract_value(pattern, clause):
        if not clause:
            return None
        m = re.search(pattern, clause)
        if m:
            return float(m.group(1).replace(',', ''))
        return None

    def extract_yoy(clause):
        """Extract YoY from a clause; negative if 下降."""
        if not clause:
            return None
        # Match: 比2024年同期（星期五）增长7.3%  OR  比2024年同期增长7.3%
        m = re.search(r'比\d{4}年同期(?:[（(][^）)]+[）)])?\s*(增长|下降)\s*(\d+(?:\.\d+)?)%', clause)
        if not m:
            # fallback: 同比...增长/下降
            m = re.search(r'同比(?:[（(][^）)]+[）)])?\s*(增长|下降)\s*(\d+(?:\.\d+)?)%', clause)
        if m:
            val = float(m.group(2))
            return -val if m.group(1) == '下降' else val
        return None

    # Total flow
    tc = find_clause(['全社会跨区域人员流动量'])
    record["total_flow"] = extract_value(r'全社会跨区域人员流动量\s*(\d+(?:\.\d+)?)\s*万人次', tc)
    record["total_flow_yoy"] = extract_yoy(tc)

    # Railway (some articles insert a space: "铁路 客运量")
    rc = find_clause(['铁路客运量', '铁路 客运量'])
    record["railway"] = extract_value(r'铁路\s*客运量\s*(\d+(?:\.\d+)?)\s*万人次', rc)
    record["railway_yoy"] = extract_yoy(rc)

    # Highway total (some articles: "公路 人员流动量")
    hc = find_clause(['公路人员流动量', '公路 人员流动量'])
    record["highway"] = extract_value(r'公路\s*人员流动量\s*[（(]包括[^）)]+[）)]\s*(\d+(?:\.\d+)?)\s*万人次', hc)
    record["highway_yoy"] = extract_yoy(hc)

    # Waterway (some articles say "水路客运量", some "水路 客运量", some "水路73.4万人次")
    wc = find_clause(['水路客运量', '水路 客运量'])
    if wc is None:
        # Fallback: search for a clause that starts with "水路" followed by a number
        for c in clauses:
            if re.search(r'水路\s*(?:客运量)?\s*\d+(?:\.\d+)?\s*万人次', c):
                wc = c
                break
    record["waterway"] = extract_value(r'水路\s*(?:客运量)?\s*(\d+(?:\.\d+)?)\s*万人次', wc)
    record["waterway_yoy"] = extract_yoy(wc)

    # Aviation (some articles insert a space: "民航 客运量")
    ac = find_clause(['民航客运量', '民航 客运量'])
    record["aviation"] = extract_value(r'民航\s*客运量\s*(\d+(?:\.\d+)?)\s*万人次', ac)
    record["aviation_yoy"] = extract_yoy(ac)

    return record


def main():
    all_items = []
    for page in LIST_PAGES:
        url = urljoin(BASE_URL, page)
        print(f"[list] Fetching {url}")
        html = fetch(url)
        parser = ListPageParser()
        parser.feed(html)
        all_items.extend(parser.items)
        time.sleep(REQUEST_DELAY)

    print(f"[list] Found {len(all_items)} data articles")

    records = []
    for item in all_items:
        article_url = urljoin(BASE_URL, item["href"])
        print(f"[article] Fetching {article_url}")
        html = fetch(article_url)
        record = parse_article(html, article_url, item["publish_date"])
        records.append(record)
        time.sleep(REQUEST_DELAY)

    # Filter: keep only actual 2025 Spring Festival travel data
    def is_valid(r):
        d = r.get("date")
        if not d:
            return False
        # Must fall within 2025 Spring Festival window
        if not ("2025-01-14" <= d <= "2025-02-22"):
            return False
        # Skip forecast-only articles (e.g. "预计")
        if "预计" in (r.get("title") or "") and d == "2025-01-14":
            return False
        return True

    records = [r for r in records if is_valid(r)]
    records.sort(key=lambda r: r.get("date") or "")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"[scraper] Saved {len(records)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
