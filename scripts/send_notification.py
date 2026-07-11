#!/usr/bin/env python3
"""Send a Datavoy notification to all confirmed subscribers."""
import argparse
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

    parser = argparse.ArgumentParser(description="Send a Datavoy notification.")
    parser.add_argument("title", help="Chinese title")
    parser.add_argument("message", help="Chinese message body")
    parser.add_argument("link", nargs="?", default="https://shiyuantian.co/datavoy/", help="Link URL")
    parser.add_argument("--title-en", dest="title_en", help="English title")
    parser.add_argument("--message-en", dest="message_en", help="English message body")
    args = parser.parse_args()

    payload = {
        "title": args.title,
        "message": args.message,
        "link": args.link,
    }
    if args.title_en:
        payload["title_en"] = args.title_en
    if args.message_en:
        payload["message_en"] = args.message_en

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
