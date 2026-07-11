#!/usr/bin/env python3
"""Export Datavoy subscribers to a CSV file in the exports/ directory."""
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime

URL = "https://shiyuantian.co/api/subscribers"
EXPORT_DIR = "exports"


def main():
    secret = os.environ.get("NOTIFY_SECRET")
    if not secret:
        print("Error: set NOTIFY_SECRET environment variable.", file=sys.stderr)
        sys.exit(1)

    req = urllib.request.Request(
        URL,
        headers={
            "Authorization": f"Bearer {secret}",
            "User-Agent": "DatavoyAdmin/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(EXPORT_DIR, exist_ok=True)
    filename = os.path.join(EXPORT_DIR, f"subscribers_{datetime.now().strftime('%Y-%m-%d')}.csv")

    fieldnames = ["status", "email", "first_name", "last_name", "company", "job_title", "phone", "created"]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in data.get("subscribers", []):
            writer.writerow({k: s.get(k, "") for k in fieldnames})

    print(f"Exported {data.get('total', 0)} subscribers to {filename}")
    print(f"Confirmed: {data.get('confirmed', 0)}, Pending: {data.get('pending', 0)}, Unsubscribed: {data.get('unsubscribed', 0)}")


if __name__ == "__main__":
    main()
