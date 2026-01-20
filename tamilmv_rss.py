import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree
import time, json, os
from urllib.parse import parse_qs, urlparse

# ================= CONFIG =================
BASE_URL = "https://www.1tamilmv.haus/"   # 🔴 ONE BASE URL ONLY
OUT_FILE = "tamilmv.xml"
STATE_FILE = "state.json"

TOPIC_LIMIT = 50              # 🚨 High → no post miss
TOPIC_DELAY = 3               # Seconds between topic fetch
MAX_MAGNETS_PER_RUN = 25      # 🚑 Flood protection (per cron)
MAX_SIZE_GB = 4               # ⛔ Skip >4GB torrents
# ==========================================

# Cloudflare bypass
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ---------------- Load state ----------------
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {"magnets": []}

processed = set(state.get("magnets", []))

# ---------------- RSS setup ----------------
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "1TamilMV Torrent RSS"
SubElement(channel, "link").text = BASE_URL
SubElement(channel, "description").text = "Auto RSS – No Miss – Below 4GB"
SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
    "%a, %d %b %Y %H:%M:%S GMT"
)

# ---------------- Fetch homepage ----------------
home = scraper.get(BASE_URL, timeout=30)
soup = BeautifulSoup(home.text, "lxml")

# Collect latest topics (NO SKIP)
posts = []
for a in soup.select("a[href*='forums/topic']"):
    title = a.get_text(strip=True)
    link = a["href"]
    posts.append((title, link))

posts = posts[:TOPIC_LIMIT]

def magnet_size_gb(magnet):
    qs = parse_qs(urlparse(magnet).query)
    if "xl" in qs:
        return int(qs["xl"][0]) / (1024 ** 3)
    return None

# ---------------- Scrape topics ----------------
added_count = 0

for title, post_url in posts:
    if added_count >= MAX_MAGNETS_PER_RUN:
        print("🚑 Flood limit reached")
        break

    try:
        time.sleep(TOPIC_DELAY)

        page = scraper.get(post_url, timeout=30)
        psoup = BeautifulSoup(page.text, "lxml")

        # 🔥 VERY IMPORTANT
        # Same post ni malli malli open chestham
        # But magnet already state.json lo unte skip
        for a in psoup.find_all("a", href=True):
            magnet = a["href"]

            if not magnet.startswith("magnet:?"):
                continue

            if magnet in processed:
                continue   # ✅ Magnet-level protection

            size = magnet_size_gb(magnet)
            if size and size > MAX_SIZE_GB:
                continue

            # Add RSS item
            item = SubElement(channel, "item")
            SubElement(item, "title").text = (
                f"{title} [{round(size,2)}GB]" if size else title
            )
            SubElement(item, "link").text = magnet
            SubElement(item, "guid").text = magnet
            SubElement(item, "pubDate").text = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

            processed.add(magnet)
            added_count += 1
            print("➕ ADDED:", title, size)

            if added_count >= MAX_MAGNETS_PER_RUN:
                break

    except Exception as e:
        print("ERROR:", title, e)

# ---------------- SAVE FILES (ALWAYS) ----------------
ElementTree(rss).write(OUT_FILE, encoding="utf-8", xml_declaration=True)

with open(STATE_FILE, "w") as f:
    json.dump({"magnets": list(processed)}, f, indent=2)

print(f"✅ DONE | Added this run: {added_count}")
