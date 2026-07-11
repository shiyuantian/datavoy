#!/usr/bin/env python3
"""List Datavoy email subscribers via the Cloudflare Worker admin endpoint."""
import json
import os
import sys
import urllib.request

URL = "https://shiyuantian.co/api/subscribers"


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

    print(f"Total: {data.get('total', 0)}")
    print(f"Confirmed: {data.get('confirmed', 0)}")
    print(f"Pending:   {data.get('pending', 0)}")
    print(f"Unsubscribed: {data.get('unsubscribed', 0)}")
    print()
    for s in data.get("subscribers", []):
        phone = s.get("phone") or "—"
        name = " ".join(filter(None, [s.get("first_name"), s.get("last_name")])) or "—"
        company = s.get("company") or "—"
        job_title = s.get("job_title") or "—"
        print(f"{s.get('status'):12} {s.get('email'):30} name={name:20} company={company:20} title={job_title:16} phone={phone}")


if __name__ == "__main__":
    main()
