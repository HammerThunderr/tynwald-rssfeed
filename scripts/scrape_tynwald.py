"""
Tynwald RSS Scraper — Rate-Limited Version
-------------------------------------------
Fetches Tynwald RSS feeds with delays and retries to avoid 429 errors.
Saves JSON files to data/ folder.

Place at: scripts/scrape_tynwald.py in your tynwald-rssfeed repo.
"""

import requests
import json
import os
import re
import time
import random
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

# All Tynwald RSS feeds — keys match the Flutter app expectations
FEEDS = {
    "hansard":       "https://tynwald.org.im/rss?site=/business/hansard&list=2020-2040",
    "papers":        "https://tynwald.org.im/rss?site=/business/papers&list=current",
    "petitions":     "https://tynwald.org.im/rss?site=/business/petitions",
    "questions":     "https://tynwald.org.im/rss?site=/business/qpapers",
    "orders":        "https://tynwald.org.im/rss?site=/business/orderpaper",
    "votes":         "https://tynwald.org.im/rss?site=/business/votes",
    "parliamentary": "https://tynwald.org.im/rss?site=/business",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IOM-Jobs-App/1.0; +https://github.com/HammerThunderr/iom-jobs-flutter)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",   # Don't hold connection open
}

# Rate-limiting config
DELAY_BETWEEN_FEEDS = 8       # seconds between each feed request
MAX_RETRIES = 3               # retry up to 3 times if 429
RETRY_BASE_DELAY = 30         # seconds — exponential backoff: 30, 60, 120


def fetch_with_retry(url, retries=MAX_RETRIES):
    """Fetch URL with exponential backoff retry on 429."""
    for attempt in range(retries):
        try:
            print(f"  Attempt {attempt + 1}/{retries}: {url[:80]}...")
            resp = requests.get(url, headers=HEADERS, timeout=30)

            if resp.status_code == 429:
                # Rate limited — wait and retry
                wait = RETRY_BASE_DELAY * (2 ** attempt) + random.randint(5, 15)
                print(f"  ⚠ 429 Rate Limited. Waiting {wait}s before retry...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            print(f"  ✓ Success ({len(resp.text)} bytes)")
            return resp.text

        except requests.HTTPError as e:
            if e.response.status_code == 429:
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"  ⚠ HTTPError 429. Waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  ✗ HTTPError: {e}")
            return None

        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {str(e)[:80]}")
            if attempt < retries - 1:
                time.sleep(5)

    return None


def parse_rss(xml_text):
    """Parse RSS XML to list of items."""
    items = []
    try:
        # Strip BOM if present
        if xml_text.startswith('\ufeff'):
            xml_text = xml_text[1:]

        root = ET.fromstring(xml_text)
        channel = root.find('channel')
        if channel is None:
            return items

        for item in channel.findall('item'):
            title = item.findtext('title', '').strip()
            link  = item.findtext('link', '').strip()
            desc  = item.findtext('description', '').strip()
            pub   = item.findtext('pubDate', '').strip()

            # Clean description — remove HTML
            desc = re.sub(r'<[^>]+>', '', desc).strip()
            desc = re.sub(r'\s+', ' ', desc)

            if title:
                items.append({
                    "title":       title,
                    "url":         link,
                    "description": desc,
                    "pubDate":     pub,
                })
    except ET.ParseError as e:
        print(f"  ✗ XML parse error: {e}")
    return items


def main():
    os.makedirs("data", exist_ok=True)

    success_count = 0
    fail_count = 0

    for i, (key, url) in enumerate(FEEDS.items()):
        print(f"\n[{i+1}/{len(FEEDS)}] Fetching {key}")

        xml = fetch_with_retry(url)

        if xml:
            items = parse_rss(xml)
            data = {
                "success": True,
                "updated": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "key": key,
                "count": len(items),
                "items": items,
            }
            print(f"  ✓ Parsed {len(items)} items")
            success_count += 1
        else:
            # Don't overwrite existing good data on failure
            existing_path = f"data/tynwald_{key}.json"
            if os.path.exists(existing_path):
                print(f"  ⚠ Keeping existing data — fetch failed")
                continue
            else:
                data = {
                    "success": False,
                    "error":   "Failed to fetch after retries (likely rate-limited)",
                    "updated": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                    "fetchedAt": datetime.now(timezone.utc).isoformat(),
                    "key":     key,
                    "items":   [],
                }
                fail_count += 1

        # Save JSON
        path = f"data/tynwald_{key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved {path}")

        # Wait between feeds (except after last one)
        if i < len(FEEDS) - 1:
            wait = DELAY_BETWEEN_FEEDS + random.randint(0, 4)
            print(f"  ⏳ Waiting {wait}s before next feed...")
            time.sleep(wait)

    print(f"\n=== Done: {success_count} OK, {fail_count} failed ===")


if __name__ == "__main__":
    main()
