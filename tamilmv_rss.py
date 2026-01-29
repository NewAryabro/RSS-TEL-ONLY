import cloudscraper, time, json, os
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from xml.etree.ElementTree import Element, SubElement, ElementTree

# ================= CONFIG =================
BASE_URL = "https://www.1tamilmv.rsvp/"
OUT_FILE = "tamilmv.xml"
STATE_FILE = "state.json"

TOPIC_LIMIT = 120          # scan many posts → no miss
TOPIC_DELAY = 2            # seconds
MAX_PER_RUN = 25           # flood protection (cron safe)

MOVIE_MAX_GB = 4           # movies <= 4GB
SERIES_MIN_GB = 4          # series >= 4GB allowed
# =========================================

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ================= STATE =================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {"magnets": []}

seen_magnets = set(state.get("magnets", []))

# ================= RSS =================
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "1TamilMV Torrent RSS"
SubElement(channel, "link").text = BASE_URL
SubElement(channel, "description").text = "Auto RSS – No Miss – Smart Size Filter"
SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
    "%a, %d %b %Y %H:%M:%S GMT"
)

# ================= HELPERS =================
def size_gb(magnet):
    qs = parse_qs(urlparse(magnet).query)
    if "xl" in qs:
        try:
            return int(qs["xl"][0]) / (1024 ** 3)
        except:
            return None
    return None

def is_series(title):
    t = title.lower()
    return any(x in t for x in [
        "season", "s01", "s02", "s03", "episode", "ep", "web series"
    ])

# ================= FETCH POSTS =================
home = scraper.get(BASE_URL, timeout=30)
soup = BeautifulSoup(home.text, "lxml")

post_links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "topic" in href:
        if not href.startswith("http"):
            href = BASE_URL.rstrip("/") + "/" + href.lstrip("/")
        post_links.append(href)

# remove duplicates, keep latest
post_links = list(dict.fromkeys(post_links))[:TOPIC_LIMIT]
print("POSTS FOUND:", len(post_links))

# ================= SCRAPE =================
added = 0

for post_url in post_links:
    if added >= MAX_PER_RUN:
        break

    try:
        time.sleep(TOPIC_DELAY)

        page = scraper.get(post_url, timeout=30)
        psoup = BeautifulSoup(page.text, "lxml")

        h1 = psoup.find("h1")
        title = h1.get_text(strip=True) if h1 else psoup.title.get_text(strip=True)

        for a in psoup.find_all("a", href=True):
            magnet = a["href"]

            if not magnet.startswith("magnet:?"):
                continue
            if magnet in seen_magnets:
                continue

            size = size_gb(magnet)

            # ---------- SIZE RULES ----------
            if size is not None:
                if is_series(title):
                    if size < SERIES_MIN_GB:
                        continue
                else:
                    if size > MOVIE_MAX_GB:
                        continue
            # --------------------------------

            item = SubElement(channel, "item")
            SubElement(item, "title").text = (
                f"{title} [{round(size,2)}GB]" if size else title
            )
            SubElement(item, "link").text = magnet
            SubElement(item, "guid").text = magnet
            SubElement(item, "pubDate").text = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

            seen_magnets.add(magnet)
            added += 1
            print("➕ ADDED:", title)

            if added >= MAX_PER_RUN:
                break

    except Exception as e:
        print("ERROR:", post_url, e)

# ================= SAVE =================
ElementTree(rss).write(OUT_FILE, encoding="utf-8", xml_declaration=True)

with open(STATE_FILE, "w") as f:
    json.dump({"magnets": list(seen_magnets)}, f, indent=2)

print(f"✅ DONE | Added this run: {added}")
