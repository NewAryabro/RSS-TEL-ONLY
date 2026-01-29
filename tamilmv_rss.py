import cloudscraper, time, json, os
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from xml.etree.ElementTree import Element, SubElement, ElementTree

BASE_URL = "https://www.1tamilmv.rsvp/"
OUT_FILE = "tamilmv.xml"
STATE_FILE = "state.json"

TOPIC_LIMIT = 100        # 🔥 never miss
TOPIC_DELAY = 2
MAX_PER_RUN = 25

MOVIE_MAX_GB = 4         # 🎬 movie rule
SERIES_MIN_GB = 4        # 📺 series allowed

scraper = cloudscraper.create_scraper()

# ---------- STATE ----------
if os.path.exists(STATE_FILE):
    state = json.load(open(STATE_FILE))
else:
    state = {"posts": {}, "magnets": []}

seen_posts = state["posts"]
seen_magnets = set(state["magnets"])

# ---------- RSS ----------
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")
SubElement(channel, "title").text = "1TamilMV Torrent RSS"
SubElement(channel, "link").text = BASE_URL
SubElement(channel, "description").text = "Auto RSS – No Miss – Smart Size Filter"
SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
    "%a, %d %b %Y %H:%M:%S GMT"
)

# ---------- HELPERS ----------
def size_gb(magnet):
    qs = parse_qs(urlparse(magnet).query)
    if "xl" in qs:
        return int(qs["xl"][0]) / (1024 ** 3)
    return None

def is_series(title):
    return any(x in title.lower() for x in ["season", "s01", "s02", "episode", "ep"])

# ---------- FETCH POSTS ----------
home = scraper.get(BASE_URL, timeout=30)
soup = BeautifulSoup(home.text, "lxml")

post_links = []
for a in soup.find_all("a", href=True):
    if "/topic/" in a["href"]:
        link = a["href"]
        if not link.startswith("http"):
            link = BASE_URL.rstrip("/") + "/" + link.lstrip("/")
        post_links.append(link)

post_links = list(dict.fromkeys(post_links))[:TOPIC_LIMIT]

# ---------- SCRAPE ----------
added = 0

for post in post_links:
    if added >= MAX_PER_RUN:
        break

    if post not in seen_posts:
        seen_posts[post] = {"checked": 0}

    try:
        time.sleep(TOPIC_DELAY)
        page = scraper.get(post, timeout=30)
        psoup = BeautifulSoup(page.text, "lxml")
        title = psoup.title.get_text(strip=True)

        for a in psoup.find_all("a", href=True):
            magnet = a["href"]
            if not magnet.startswith("magnet:?"):
                continue
            if magnet in seen_magnets:
                continue

            size = size_gb(magnet)
            if size:
                if is_series(title):
                    if size < SERIES_MIN_GB:
                        continue
                else:
                    if size > MOVIE_MAX_GB:
                        continue

            item = SubElement(channel, "item")
            SubElement(item, "title").text = f"{title} [{round(size,2)}GB]" if size else title
            SubElement(item, "link").text = magnet
            SubElement(item, "guid").text = magnet
            SubElement(item, "pubDate").text = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

            seen_magnets.add(magnet)
            added += 1
            print("➕", title)

    except Exception as e:
        print("ERR:", post, e)

# ---------- SAVE ----------
ElementTree(rss).write(OUT_FILE, encoding="utf-8", xml_declaration=True)
json.dump(
    {"posts": seen_posts, "magnets": list(seen_magnets)},
    open(STATE_FILE, "w"),
    indent=2
)

print("✅ DONE | Added:", added)
