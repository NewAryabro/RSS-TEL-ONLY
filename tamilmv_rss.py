import cloudscraper, time, json, os, re
from bs4 import BeautifulSoup
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree, parse

# ================= CONFIG =================
BASE_URL = "https://www.1tamilmv.rsvp/"
OUT_FILE = "tamilmv.xml"
STATE_FILE = "state.json"

MAX_TOPICS = 60
MAX_ITEMS = 25
DELAY = 2

MOVIE_MAX_GB = 4
SERIES_MIN_GB = 4
# ========================================

scraper = cloudscraper.create_scraper()

# ================= STATE =================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {"magnets": []}

seen = set(state.get("magnets", []))

# ================= RSS LOAD / CREATE =================
if os.path.exists(OUT_FILE):
    tree = parse(OUT_FILE)
    rss = tree.getroot()
    channel = rss.find("channel")
else:
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "1TamilMV Torrent RSS"
    SubElement(channel, "link").text = BASE_URL
    SubElement(channel, "description").text = "Auto RSS – Telugu / English Only – Smart Filter"

# ================= HELPERS =================
def is_series(title):
    t = title.lower()
    return any(x in t for x in ["season", "s01", "s02", "s03", "episode", "ep", "series"])

def size_from_text(text):
    m = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB)', text.upper())
    if not m:
        return None
    size = float(m.group(1))
    if m.group(2) == "MB":
        size /= 1024
    return size

def clean_title(title):
    return re.sub(r"1TamilMV\s*[-–]\s*", "", title).strip()

# 🔥 LANGUAGE FILTER (TEL / ENG REQUIRED)
def is_allowed_language(title):
    t = title.lower()

    telugu = any(x in t for x in ["telugu", "+ tel", " tel +", "[tel", " tel]"])
    english = any(x in t for x in ["english", "+ eng", " eng +", "[eng", " eng]"])

    return telugu or english

# ================= FETCH HOME =================
home = scraper.get(BASE_URL, timeout=30)
soup = BeautifulSoup(home.text, "lxml")

topics = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "/topic/" in href:
        if not href.startswith("http"):
            href = BASE_URL.rstrip("/") + href
        topics.append(href)

topics = list(dict.fromkeys(topics))[:MAX_TOPICS]
print("TOPICS FOUND:", len(topics))

# ================= SCRAPE =================
added = 0

for url in topics:
    if added >= MAX_ITEMS:
        break

    try:
        time.sleep(DELAY)

        page = scraper.get(url, timeout=30)
        html = page.text
        psoup = BeautifulSoup(html, "lxml")

        raw_title = psoup.title.get_text(strip=True)
        title = clean_title(raw_title)

        print("CHECK:", title)

        # ❌ Language filter
        if not is_allowed_language(title):
            continue

        size = size_from_text(title)

        # 🎬 Size rules
        if size is not None:
            if is_series(title):
                if size < SERIES_MIN_GB:
                    continue
            else:
                if size > MOVIE_MAX_GB:
                    continue

        magnets = re.findall(r"(magnet:\?[^\s\"'<]+)", html)

        for magnet in magnets:
            if magnet in seen:
                continue

            item = SubElement(channel, "item")
            SubElement(item, "title").text = (
                f"{title} [{round(size,2)}GB]" if size else title
            )
            SubElement(item, "link").text = magnet
            SubElement(item, "guid").text = magnet
            SubElement(item, "pubDate").text = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

            seen.add(magnet)
            added += 1
            print("➕ ADDED:", title)

            if added >= MAX_ITEMS:
                break

    except Exception as e:
        print("ERROR:", url, e)

# ================= UPDATE BUILD DATE =================
last = channel.find("lastBuildDate")
if last is None:
    last = SubElement(channel, "lastBuildDate")

last.text = datetime.utcnow().strftime(
    "%a, %d %b %Y %H:%M:%S GMT"
)

# ================= SAVE =================
if added > 0:
    ElementTree(rss).write(OUT_FILE, encoding="utf-8", xml_declaration=True)
    print("RSS UPDATED")
else:
    print("NO NEW ITEMS – RSS KEPT")

with open(STATE_FILE, "w") as f:
    json.dump({"magnets": list(seen)}, f, indent=2)

print("✅ DONE | Added:", added)
