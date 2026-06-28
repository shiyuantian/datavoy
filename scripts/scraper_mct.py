"""
Scraper for Ministry of Culture and Tourism (MCT) holiday travel data.

Crawls the "焦点新闻" column at /whzx/whyw/ and extracts domestic travel
statistics disclosed for major holidays since 2023.

Output: data/mct_tourism_raw.json
"""

import json
import os
import re
import time
import urllib.request
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin
from datetime import datetime

BASE_LIST_URL = "https://www.mct.gov.cn/whzx/whyw/"
LIST_PAGES = ["index.htm"] + [f"index_{i}.htm" for i in range(1, 25)]
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(ROOT_DIR, "data", "mct_tourism_raw.json")
REQUEST_DELAY = 0.5

HOLIDAY_KEYWORDS = [
    "春节", "清明", "五一", "端午", "中秋", "国庆",
    "暑期", "元旦", "假期", "出游", "文化和旅游市场情况",
]


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
        # Some pages may use GBK; try UTF-8 first, fallback to GBK
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
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            title = attrs_dict.get("title", "")
            # Article links look like ./202305/t20230503_943504.htm
            if re.match(r"\.\/\d{6}\/t\d{8,}_\d+\.htm", href):
                self.in_target_a = True
                self.current_href = href
                self.current_title = title

    def handle_data(self, data):
        if self.in_target_a and not self.current_title:
            self.current_title = data.strip()

    def handle_endtag(self, tag):
        if tag == "a" and self.in_target_a:
            if self.current_href and self.current_title:
                self.items.append({
                    "href": self.current_href,
                    "title": self.current_title,
                })
            self.in_target_a = False
            self.current_href = None
            self.current_title = None


def parse_list_page(html: str):
    parser = ListPageParser()
    parser.feed(html)
    return parser.items


def is_holiday_article(title: str) -> bool:
    """Heuristic to detect articles that disclose holiday travel data."""
    title = title.lower()
    # Keep articles that actually report domestic travel statistics.
    data_indicators = ["国内出游", "文化和旅游市场情况", "国内旅游出游"]
    has_data_indicator = any(ind in title for ind in data_indicators)
    has_holiday = any(kw in title for kw in HOLIDAY_KEYWORDS)
    return has_data_indicator and has_holiday


def strip_html_tags(fragment: str) -> str:
    """Remove HTML tags and decode common entities."""
    txt = re.sub(r'<[^>]+>', '', fragment)
    txt = txt.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    txt = txt.replace('\r', '').replace('\t', ' ')
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt


def extract_container_text(html: str, class_or_id: str, by_id: bool = False) -> str:
    """Extract all text inside a container div, handling nested divs."""
    if by_id:
        start_pat = rf'<div[^>]*id=["\']{class_or_id}["\'][^>]*>'
    else:
        start_pat = rf'<div[^>]*class=["\']{class_or_id}["\'][^>]*>'
    start_m = re.search(start_pat, html, re.I)
    if not start_m:
        return ""

    start = start_m.end()
    depth = 1
    pos = start
    html_lower = html.lower()
    while depth > 0 and pos < len(html):
        next_open = html_lower.find('<div', pos)
        next_close = html_lower.find('</div>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            if depth == 0:
                end = next_close
                pos = next_close + 6
            else:
                pos = next_close + 6
    else:
        end = pos

    container_html = html[start:end]
    # Remove <script> and <style> fragments if any
    container_html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', container_html, flags=re.S | re.I)
    return strip_html_tags(container_html)


def extract_text_from_article(html: str) -> tuple[str, str, str]:
    """Extract publish date, title and main text from article HTML."""
    # Publish date
    pub_date = ""
    m = re.search(r'发布时间[：:]\s*(\d{4}-\d{2}-\d{2})', html)
    if not m:
        m = re.search(r'(\d{4}-\d{2}-\d{2})\s*\d{2}:\d{2}', html)
    if m:
        pub_date = m.group(1)

    # Title from <title> tag, stripping site suffix
    title = ""
    m = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
    if m:
        title = re.sub(r'_+中华人民共和国文化和旅游部.*$', '', m.group(1)).strip()

    # Try to locate the main content container used by the TRS CMS.
    main_text = ""
    for container_name, by_id in [("TRS_Editor", False), ("zoom", True)]:
        main_text = extract_container_text(html, container_name, by_id)
        if main_text:
            break

    # Fallback to concatenating all <p> paragraphs if no container found.
    if not main_text:
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S | re.I)
        texts = [strip_html_tags(p) for p in paragraphs if strip_html_tags(p)]
        main_text = '\n'.join(texts)

    return pub_date, title, main_text


def parse_numbers(text: str) -> dict:
    """Extract travel statistics from article text."""
    result = {
        "visitor_count": None,      # 亿人次
        "visitor_yoy": None,        # %
        "visitor_yoy_2019": None,   # %
        "spending": None,           # 亿元
        "spending_yoy": None,       # %
        "spending_yoy_2019": None,  # %
        "holiday_days": None,       # 假期天数
    }

    # Patterns for absolute values
    visitor_value_pattern = r'(?:全国)?国内(?:旅游)?出游(?:合计)?(?:人数|人次)?\s*(\d+(?:\.\d+)?)\s*亿(?:人次)?'
    spending_value_pattern = r'(?:国内出游总花费|国内旅游收入|实现国内旅游收入|国内游客出游总花费|国内游客出游花费)\s*(\d+(?:\.\d+)?)\s*亿元'

    # Helper: find the clause that contains the metric value, then extract a percentage from it.
    def extract_pct_for_metric(metric_pattern, pct_patterns, text):
        clauses = re.split(r'[。；\n]', text)
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            if re.search(metric_pattern, clause):
                for pct_pat in pct_patterns:
                    m = re.search(pct_pat, clause)
                    if m:
                        val = float(m.group(1))
                        if '恢复至' in pct_pat or '相当于' in pct_pat:
                            val = val - 100
                        return round(val, 2)
        return None

    # 1. 国内出游人次 (亿人次)
    m = re.search(visitor_value_pattern, text)
    if m:
        result["visitor_count"] = float(m.group(1))

    # 2. 国内出游总花费 / 国内旅游收入 (亿元)
    m = re.search(spending_value_pattern, text)
    if m:
        result["spending"] = float(m.group(1))

    # 3. 同比增长
    result["visitor_yoy"] = extract_pct_for_metric(
        visitor_value_pattern, [r'同比增长\s*([-+]?\d+(?:\.\d+)?)\s*%'], text
    )
    result["spending_yoy"] = extract_pct_for_metric(
        spending_value_pattern, [r'同比增长\s*([-+]?\d+(?:\.\d+)?)\s*%'], text
    )

    # 4. 较 2019 年同期对比（可比口径）
    yoy_2019_patterns = [
        r'(?:较|比|与)2019年(?:同期)?(?:增长|下降|减少)\s*([-+]?\d+(?:\.\d+)?)\s*%',
        r'恢复至2019年(?:同期)?的\s*(\d+(?:\.\d+)?)\s*%',
        r'相当于2019年(?:同期)?的(?:约|)(\d+(?:\.\d+)?)\s*%',
    ]
    result["visitor_yoy_2019"] = extract_pct_for_metric(visitor_value_pattern, yoy_2019_patterns, text)
    result["spending_yoy_2019"] = extract_pct_for_metric(spending_value_pattern, yoy_2019_patterns, text)

    # 5. 假期天数
    days_match = re.search(r'(?:假期|假日|节假)(?:\d+天)?\s*(\d+)\s*天', text)
    if not days_match:
        # 尝试从标题附近提取，如 "春节假日9天"
        days_match = re.search(r'(?:春节|元旦|清明|五一|端午|中秋|国庆).{0,6}(\d+)\s*天', text)
    if days_match:
        result["holiday_days"] = int(days_match.group(1))

    return result


DEFAULT_HOLIDAY_DAYS = {
    "元旦": 3, "清明": 3, "五一": 5, "端午": 3,
    "中秋": 3, "国庆": 7, "国庆中秋": 8,
}


def infer_holiday_days(holiday_name: str, year: int, parsed_days: Optional[int]) -> Optional[int]:
    """Infer holiday duration if not parsed from text."""
    if parsed_days is not None:
        return parsed_days
    if holiday_name in DEFAULT_HOLIDAY_DAYS:
        return DEFAULT_HOLIDAY_DAYS[holiday_name]
    if holiday_name == "春节":
        # Known durations for recent years
        mapping = {2023: 7, 2024: 8, 2025: 8, 2026: 9}
        return mapping.get(year)
    return None


def infer_holiday_name(title: str, publish_date: str, text: str) -> str:
    """Infer holiday name from title, date or text."""
    title_and_text = title + text[:300]

    # Combined holidays first
    if "国庆" in title_and_text and "中秋" in title_and_text:
        return "国庆中秋"

    candidates = ["春节", "清明", "五一", "端午", "中秋", "国庆", "暑期", "元旦"]
    for h in candidates:
        if h in title or h in text[:200]:
            return h

    # Fallback based on publish month
    if publish_date:
        month = int(publish_date.split('-')[1])
        mapping = {1: "元旦/春节", 4: "清明", 5: "五一", 6: "端午", 7: "暑期",
                   8: "暑期", 9: "中秋", 10: "国庆"}
        return mapping.get(month, "其他")
    return "其他"


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    all_articles = []
    seen_urls = set()

    print(f"[scraper] Crawling {len(LIST_PAGES)} list pages...")
    for page in LIST_PAGES:
        url = urljoin(BASE_LIST_URL, page)
        try:
            html = fetch(url)
            items = parse_list_page(html)
            print(f"[scraper] {page}: {len(items)} article links found")
            for it in items:
                article_url = urljoin(url, it["href"])
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                all_articles.append({
                    "url": article_url,
                    "title": it["title"],
                    "list_page": page,
                })
        except Exception as e:
            print(f"[scraper] Error fetching {url}: {e}")
        time.sleep(REQUEST_DELAY)

    print(f"[scraper] Total unique articles: {len(all_articles)}")

    holiday_articles = [a for a in all_articles if is_holiday_article(a["title"])]
    print(f"[scraper] Holiday-related articles: {len(holiday_articles)}")

    results = []
    for idx, art in enumerate(holiday_articles, 1):
        print(f"[scraper] ({idx}/{len(holiday_articles)}) {art['title']}")
        try:
            html = fetch(art["url"])
            pub_date, title, main_text = extract_text_from_article(html)
            numbers = parse_numbers(main_text)
            holiday_name = infer_holiday_name(title or art["title"], pub_date, main_text)
            year = int(pub_date.split('-')[0]) if pub_date else None
            holiday_days = infer_holiday_days(holiday_name, year, numbers["holiday_days"])

            results.append({
                "year": year,
                "holiday_name": holiday_name,
                "publish_date": pub_date,
                "title": title or art["title"],
                "source_url": art["url"],
                "visitor_count": numbers["visitor_count"],
                "visitor_yoy": numbers["visitor_yoy"],
                "visitor_yoy_2019": numbers["visitor_yoy_2019"],
                "spending": numbers["spending"],
                "spending_yoy": numbers["spending_yoy"],
                "spending_yoy_2019": numbers["spending_yoy_2019"],
                "holiday_days": holiday_days,
                "raw_text": main_text,
            })
        except Exception as e:
            print(f"[scraper] Error processing {art['url']}: {e}")
        time.sleep(REQUEST_DELAY)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[scraper] Saved {len(results)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
