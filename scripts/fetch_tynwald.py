import requests
import json
import re
import os
from datetime import datetime, timezone

FEEDS = {
    "parliamentary": "https://tynwald.org.im/rss?site=/business/pp&list=Parliamentary%20Reports",
    "votes":         "https://tynwald.org.im/rss?site=/business/vp&list=Votes%20and%20Proceedings",
    "orders":        "https://tynwald.org.im/rss?site=/business/opqp&list=Order%20Papers%20and%20Question%20Papers",
    "hansard":       "https://tynwald.org.im/rss?site=/business/hansard&list=2020-2040",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/xml, application/rss+xml, */*",
}

def parse_rss(xml_text):
    items = []
    for block in re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL):
        title = re.search(r'<title>\s*(.*?)\s*</title>', block, re.DOTALL)
        link  = re.search(r'<link>\s*(.*?)\s*</link>',   block, re.DOTALL)
        desc  = re.search(r'<description>\s*(.*?)\s*</description>', block, re.DOTALL)
        t = title.group(1).strip() if title else ""
        l = link.group(1).strip()  if link  else ""
        d = desc.group(1).strip()  if desc  else ""
        if t and l:
            items.append({"title": t, "url": l, "description": d})
    return items

os.makedirs("data", exist_ok=True)

for key, url in FEEDS.items():
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        items = parse_rss(resp.text)
        output = {
            "success": True,
            "feed": key,
            "total": len(items),
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "items": items
        }
        print(f"✓ {key}: {len(items)} items")
    except Exception as e:
        output = {
            "success": False,
            "feed": key,
            "error": str(e),
            "items": []
        }
        print(f"✗ {key}: {e}")

    with open(f"data/tynwald_{key}.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

print("Done.")
