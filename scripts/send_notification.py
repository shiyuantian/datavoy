#!/usr/bin/env python3
"""Send a Datavoy notification to all confirmed subscribers."""
import json
import os
import sys
import urllib.request

URL = "https://shiyuantian.co/api/notify"


def main():
    secret = os.environ.get("NOTIFY_SECRET")
    if not secret:
        print("Error: set NOTIFY_SECRET environment variable.", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 3:
        print("Usage: python3 send_notification.py '<标题>' '<正文>' [链接]", file=sys.stderr)
        print('Example: python3 send_notification.py "Datavoy 更新" "端午数据已上线。" "https://shiyuantian.co/datavoy/"', file=sys.stderr)
        sys.exit(1)

    title = sys.argv[1]
    message = sys.argv[2]
    link = sys.argv[3] if len(sys.argv) > 3 else "https://shiyuantian.co/datavoy/"

    payload = {"title": title, "message": message, "link": link}
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
            "User-Agent": "DatavoyNotify/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            print(body)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
