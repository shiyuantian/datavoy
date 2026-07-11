#!/usr/bin/env python3
"""Send a test notification via the Cloudflare Worker /api/notify endpoint."""
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

    payload = {
        "title": "Datavoy 测试通知",
        "message": "密钥已迁移到 Secret，邮件通知流程跑通。",
        "link": "https://shiyuantian.co/datavoy/",
    }

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
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
