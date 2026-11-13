#!/usr/bin/env python3
"""Collect Wenatchee-area events from many public calendars into data/events.json.

Standard library only, so GitHub Actions needs no installs. Run: python scripts/collect.py
Writes:
  data/events.json      everything the web page shows
  data/plan-ahead.ics   subscribable calendar of concerts / big ticketed events
  data/new-big.json     big events first seen in this run (used for the GitHub alert)
"""
import gzip, hashlib, html, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
try:
    with open(os.path.join(DATA, "region.json")) as _f:
        _REGION_EARLY = json.load(_f)
except Exception:
    _REGION_EARLY = {}
TZ = ZoneInfo(_REGION_EARLY.get("tz", "America/Los_Angeles"))
NOW = datetime.now(TZ)
HORIZON = NOW + timedelta(days=400)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36 wenatchee-activities/1.0 (+https://github.com/joemarcouxid/wenatchee-activities)")

# ---------------------------------------------------------------- geography
# (area shown in the app, words that identify it, ZIP codes)
AREAS = [
    ("Leavenworth", ["lake wenatchee", "leavenworth", "red barn", "wenatchee river institute", "snowy owl", "icicle creek center",
                     "sleeping lady", "festhalle", "water from wine", "mountain springs lodge", "a book for all seasons", "icicle brewing",
                     "kris kringl", "boulder bend", "front street park", "munchen haus", "münchen haus", "goose ridge: leavenworth", "plain, wa", "plain wa", "icicle road", "front street, leavenworth"], ["98826"]),
    ("East Wenatchee", ["east wenatchee", "rock island", "orondo"], ["98802", "98850", "98843"]),
    ("Wenatchee", ["weinstein beverage", "town toyota", "pybus", "numerica", "convention center", "wenatchee valley college",
                   "riverfront park", "pinnacle beerworks", "wenatchee", "malaga", "mission ridge", "sunnyslope"], ["98801", "98807", "98828"]),
    ("Cashmere", ["cashmere", "peshastin", "dryden", "monitor, wa"], ["98815", "98847", "98821", "98836"]),
    ("Entiat", ["entiat", "ardenvoir"], ["98822", "98811"]),
    ("Chelan", ["chelan", "manson", "stehekin"], ["98816", "98831", "98817", "98852"]),
    ("Quincy", ["quincy", "george, wa", "george wa", "gorge amphitheat", "the gorge", "crescent bar", "cave b", "sunland estates"], ["98848", "98824"]),
]
AREA_NAMES = [a[0] for a in AREAS]
# Places that contain our town names but are elsewhere
NOT_HERE = ["quincy, ma", "quincy, il", "quincy, ca", "quincy, fl", "chelan county pud", "seattle", "spokane", "yakima",
            "ellensburg", "moses lake", "ephrata", "twisp", "winthrop", "omak", "tacoma", "bellevue", "everett", "kennewick",
            "darrington", "royal city", "warden", "waterville", "brewster", "grand coulee", "coulee city", "republic", "curlew", "bothell",
            "redmond", "portland", "boise", "walla walla", "richland", "pasco", "cle elum", "roslyn", "bellingham", "olympia"]


REGION = {}
_rp = os.path.join(DATA, "region.json")
if os.path.exists(_rp):
    with open(_rp) as _f:
        REGION = json.load(_f)
    AREAS = [(x["name"], x["words"], x.get("zips", [])) for x in REGION["areas"]]
    NOT_HERE = REGION.get("notHere", [])
AREA_NAMES = [a[0] for a in AREAS]


def find_area(*texts):
    t = " ".join(x for x in texts if x).lower()
    if not t:
        return None
    # exact ZIP codes first, then venue/town words, then broad ZIP ranges (e.g. 598xx)
    for name, _, zips in AREAS:
        for z in zips:
            if z.isdigit() and re.search(r"\b%s\b" % z, t):
                return name
    for name, words, _ in AREAS:
        for w in words:
            if w in t:
                return name
    for name, _, zips in AREAS:
        for z in zips:
            if not z.isdigit() and re.search(r"\b%s\b" % z, t):
                return name
    return None


def far_away(*texts):
    t = " ".join(x for x in texts if x).lower()
    return any(w in t for w in NOT_HERE) and not find_area(t)


# ---------------------------------------------------------------- categories
CATS = [
    ("food", ["food truck", "brew", "beer", "wine", "winery", "cider", "tasting", "dinner", "brunch", "breakfast", "bbq",
              "chili", "taco", "culinary", "distill", "happy hour", "pizza", "taproom", "cook", "feast", "pancake", "coffee", "bakery", "oyster", "crab"]),
    ("music", ["concert", "live music", "band", "music", " dj", "symphony", "orchestra", "acoustic", "karaoke", "open mic",
               "jazz", "bluegrass", "choir", "singer", "songwriter", "tour", "tribute", "rock", "country", "accordion", "mariachi", "edm", "festival lineup"]),
    ("family", ["kids", "kid ", "family", "children", "toddler", "story time", "storytime", "santa", "youth", "teen", "all ages", "baby", "lego", "egg hunt", "trick or treat", "pumpkin"]),
    ("outdoors", ["hike", "hiking", "trail", "ski", "snowshoe", "bike", "biking", "cycling", "river", "nature", "bird", "paddle",
                  "climb", "fishing", "derby", "kayak", "walk", "garden", "wildflower", "snow"]),
    ("sports", ["5k", "10k", "half marathon", "marathon", "race", "fun run", "tournament", " vs ", " vs.", "hockey", "wild ",
                "applesox", "basketball", "football", "soccer", "volleyball", "rodeo", "golf", "triathlon", "pickleball"]),
    ("arts", ["theater", "theatre", "art ", "arts", "gallery", "museum", "film", "movie", "comedy", "dance", "ballet",
              "craft", "workshop", "glassblowing", "paint night", "painting", "book signing", "poetry", "musical", "play ", "improv", "author", "pottery", "photography"]),
    ("markets", ["market", "bazaar", "fair", "farmers", "vendor", "swap", "flea", "holiday shopping", "artisan"]),
    ("festivals", ["festival", "fest", "parade", "celebration", "oktoberfest", "christmas", "village of lights", "holiday", "karneval",
                   "fireworks", "tree lighting", "winterfest", "4th of july", "fourth of july", "blossom", "salmon fest", "halloween", "new year"]),
]
BIG_VENUES = ["gorge amphitheat", "the gorge", "town toyota center", "numerica", "performing arts center", "festhalle",
              "snowy owl theater", "icicle creek center", "convention center", "cave b", "leavenworth summer theater", "ski hill amphitheater"]
BIG_VENUES = REGION.get("bigVenues", BIG_VENUES)
TICKET_WORDS = ["tickets", "ticket", "on sale", "presale", "pre-sale", "sold out", "reserved seating", "general admission", "box office"]


def categorize(e):
    t = " " + " ".join([e["title"], e.get("desc", ""), " ".join(e.get("tags", [])), e.get("venue", "")]).lower() + " "
    cats = [c for c, words in CATS if any(re.search(r"(?<![a-z0-9])" + re.escape(w.strip()) + (r"\b" if w.endswith(" ") else ""), t) for w in words)]
    if not cats:
        cats = ["community"]
    e["cats"] = cats[:3]
    e["foodTruck"] = "food truck" in t or "food trucks" in t
    cost = (e.get("cost") or "").lower()
    e["free"] = bool(re.search(r"\bfree\b", cost) or cost.strip() in ("0", "$0", "0.00", "$0.00")
                     or re.search(r"\b(free admission|free event|free and open|free to attend|admission is free|free entry)\b", t))
    ticketed = bool(e.get("ticketUrl")) or any(w in t for w in TICKET_WORDS) or bool(re.search(r"\$\s?\d", cost + t))
    big_venue = any(v in t for v in BIG_VENUES)
    showy = any(c in e["cats"] for c in ("music", "arts", "festivals", "sports"))
    e["ticketed"] = ticketed and not e["free"]
    lesson = re.search(r"\b(class|classes|workshop|lesson|camp|yoga|make a|make your own|date night|clinic|meeting|bingo|trivia|happy hour|open mic|demo|skate|storytime|story time|club|book club|meetup|support group|tutoring|practice|tryout|volunteer)", e["title"].lower())
    e["big"] = bool(not lesson and (big_venue or (not e["free"] and (e.get("_concerts") or (e["ticketed"] and showy)))))


# ---------------------------------------------------------------- fetching
def fetch(url, accept="*/*", timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip",
                                               "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def clean(s, limit=None):
    if not s:
        return ""
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s)))
    s = s.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";")
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s


def parse_dt(v):
    """Accept ISO strings like 2026-11-13, 2026-11-13 19:00:00, 2026-11-13T19:00:00-08:00. Returns (datetime, all_day)."""
    if not v:
        return None, False
    v = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        d = date.fromisoformat(v)
        return datetime(d.year, d.month, d.day, tzinfo=TZ), True
    v = v.replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", v)
        if not m:
            return None, False
        dt = datetime.fromisoformat(m.group(1) + "T" + m.group(2))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ), False


# ---------------------------------------------------------------- strategies
def strat_tribe(base, *_):
    base = base.rstrip("/")
    out, page = [], 1
    start = NOW.strftime("%Y-%m-%d 00:00:00")
    end = HORIZON.strftime("%Y-%m-%d 23:59:59")
    while page <= 40:
        q = urllib.parse.urlencode({"per_page": 50, "page": page, "start_date": start, "end_date": end})
        data = json.loads(fetch(f"{base}/wp-json/tribe/events/v1/events?{q}", "application/json"))
        for ev in data.get("events", []):
            v = ev.get("venue") or {}
            if isinstance(v, list):
                v = v[0] if v else {}
            img = ev.get("image") or {}
            out.append({
                "title": clean(ev.get("title")),
                "start": ev.get("start_date"), "end": ev.get("end_date"), "allDay": bool(ev.get("all_day")),
                "url": ev.get("url"), "desc": clean(ev.get("description"), 300), "cost": clean(ev.get("cost")),
                "venue": clean(v.get("venue")), "address": " ".join(clean(v.get(k)) for k in ("address", "city", "zip") if v.get(k)),
                "tags": [clean(c.get("name")) for c in ev.get("categories", [])],
                "image": img.get("url") if isinstance(img, dict) else None,
                "ticketUrl": ev.get("website") or None,
            })
        if page >= int(data.get("total_pages") or 1):
            break
        page += 1
    return out


def unfold_ics(text):
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def ics_dt(prop, value):
    tzid = re.search(r"TZID=([^;:]+)", prop)
    if re.fullmatch(r"\d{8}", value):
        d = datetime.strptime(value, "%Y%m%d")
        return d.replace(tzinfo=TZ).isoformat(), True
    value = value.rstrip()
    utc = value.endswith("Z")
    d = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if utc:
        d = d.replace(tzinfo=timezone.utc)
    else:
        try:
            d = d.replace(tzinfo=ZoneInfo(tzid.group(1).strip('"'))) if tzid else d.replace(tzinfo=TZ)
        except Exception:
            d = d.replace(tzinfo=TZ)
    return d.astimezone(TZ).isoformat(), False


def strat_ical(*urls):
    out = []
    for url in urls:
        out += _ical_text(fetch(url, "text/calendar"))
    return out


def _ical_text(text):
    out = []
    if True:
        cur = None
        for line in unfold_ics(text):
            if line.startswith("BEGIN:VEVENT"):
                cur = {"tags": []}
            elif line.startswith("END:VEVENT") and cur is not None:
                if cur.get("title") and cur.get("start"):
                    out.append(cur)
                cur = None
            elif cur is not None and ":" in line:
                prop, val = line.split(":", 1)
                name = prop.split(";")[0].upper()
                if name == "SUMMARY":
                    cur["title"] = clean(val)
                elif name == "DTSTART":
                    cur["start"], cur["allDay"] = ics_dt(prop, val)
                elif name == "DTEND":
                    cur["end"], _ = ics_dt(prop, val)
                elif name == "DESCRIPTION":
                    cur["desc"] = clean(val, 300)
                elif name == "LOCATION":
                    loc = clean(val)
                    cur["venue"] = loc.split(",")[0]
                    cur["address"] = loc
                elif name == "URL":
                    cur["url"] = val.strip()
                elif name == "CATEGORIES":
                    cur["tags"] = [clean(c) for c in val.split(",")]
                elif name == "X-TICKETS-URL":
                    cur["ticketUrl"] = val.strip()
                elif name == "X-COST":
                    cur["cost"] = clean(val)
                elif name == "ATTACH" and "image" in prop.lower():
                    cur["image"] = val.strip()
    # an all-day DTEND is exclusive; pull it back one day
    for e in out:
        if e.get("allDay") and e.get("end"):
            d, _ = parse_dt(e["end"])
            if d:
                e["end"] = (d - timedelta(days=1)).isoformat()
    return out


class _LD(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self._on, self._buf, self.links = [], False, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._on, self._buf = True, []
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "script" and self._on:
            self.blocks.append("".join(self._buf))
            self._on = False

    def handle_data(self, data):
        if self._on:
            self._buf.append(data)


EVENT_TYPES = re.compile(r"Event$|^Festival$")


def _walk_ld(node, acc):
    if isinstance(node, list):
        for n in node:
            _walk_ld(n, acc)
    elif isinstance(node, dict):
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and EVENT_TYPES.search(x) for x in types) and node.get("startDate"):
            acc.append(node)
        for k in ("@graph", "itemListElement", "item", "subEvent", "events", "mainEntity"):
            if k in node:
                _walk_ld(node[k], acc)


def _ld_event(n, page_url):
    loc = n.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if isinstance(loc, str):
        loc = {"name": loc}
    addr = loc.get("address") or ""
    if isinstance(addr, dict):
        addr = " ".join(str(addr.get(k, "")) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode"))
    offers = n.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price") or offers.get("lowPrice")
    cost = ""
    if price not in (None, ""):
        cost = "Free" if str(price) in ("0", "0.0", "0.00") else f"${price}"
    img = n.get("image")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url")
    t = n.get("@type")
    return {
        "title": clean(n.get("name")), "start": n.get("startDate"), "end": n.get("endDate"),
        "url": urllib.parse.urljoin(page_url, n.get("url") or page_url), "desc": clean(n.get("description"), 300),
        "venue": clean(loc.get("name")), "address": clean(addr), "cost": cost, "image": img,
        "ticketUrl": offers.get("url"), "tags": [x for x in (t if isinstance(t, list) else [t]) if x and x != "Event"],
    }


def strat_jsonld(*urls):
    out = []
    for url in urls:
        try:
            p = _LD()
            p.feed(fetch(url, "text/html"))
        except Exception as ex:
            if len(urls) == 1:
                raise
            print(f"   ! {url}: {ex}")
            continue
        acc = []
        for b in p.blocks:
            try:
                _walk_ld(json.loads(b.strip().rstrip(";")), acc)
            except Exception:
                continue
        out += [_ld_event(n, url) for n in acc]
        time.sleep(1)
    return out


def strat_discover(url, *_):
    """Look on the page for a calendar feed and use it."""
    p = _LD()
    p.feed(fetch(url, "text/html"))
    acc = []
    for b in p.blocks:
        try:
            _walk_ld(json.loads(b), acc)
        except Exception:
            pass
    if acc:
        return [_ld_event(n, url) for n in acc]
    feeds = []
    for h in p.links:
        hl = h.lower()
        if "ical" in hl or hl.endswith(".ics") or hl.startswith("webcal:"):
            feeds.append(urllib.parse.urljoin(url, h.replace("webcal://", "https://")))
        if "wp-json/tribe/events" in hl:
            return strat_tribe(h.split("/wp-json")[0])
    for f in dict.fromkeys(feeds):
        try:
            evs = strat_ical(f)
            if evs:
                return evs
        except Exception:
            continue
    return []


def strat_libcal(base, *_):
    """Springshare LibCal public event list (JSON)."""
    out, page = [], 1
    while page <= 30:
        q = urllib.parse.urlencode({"c": -1, "date": "0000-00-00", "perpage": 48, "page": page, "audience": "", "cats": "", "camps": "", "inc": 0})
        data = json.loads(fetch(f"{base.rstrip('/')}/ajax/calendar/list?{q}", "application/json"))
        res = data.get("results") or []
        for r in res:
            out.append({"title": clean(r.get("title")), "start": r.get("startdt"), "end": r.get("enddt"), "allDay": bool(r.get("all_day")),
                        "url": r.get("url"), "desc": clean(r.get("shortdesc") or r.get("description"), 300),
                        "venue": clean(f"{r.get('campus') or ''} Library {r.get('location') or ''}".strip()),
                        "address": clean(r.get("campus")), "cost": clean(r.get("registration_cost")),
                        "tags": [clean(x.get("name")) for x in (r.get("categories_arr") or [])]})
        if not res or page * 48 >= int(data.get("total_results") or 0):
            break
        page += 1
    return out


def strat_chambermaster(base, *_):
    """GrowthZone / ChamberMaster: list upcoming events, then read each event's iCal file."""
    base = base.rstrip("/")
    f, t = NOW.strftime("%m/%d/%Y"), (NOW + timedelta(days=365)).strftime("%m/%d/%Y")
    page = fetch(f"{base}/events?from={f}&to={t}&o=alpha", "text/html")
    slugs = list(dict.fromkeys(re.findall(r"/events/details/([\w-]+-\d+)", page)))[:80]
    out = []
    for slug in slugs:
        try:
            ics = fetch(f"{base}/events/addtocalendar/{slug}?format=ICal", "text/calendar")
        except Exception:
            continue
        for e in _ical_text(ics):
            e["url"] = e.get("url") or f"{base}/events/details/{slug}"
            out.append(e)
        time.sleep(0.4)
    return out


# ---------------------------------------------------------------- social posts
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
EVENTISH = re.compile(r"food truck|truck|market|concert|live music|\bband\b|festival|\bfest\b|event|\bshow\b|fundraiser|bazaar|parade|"
                      r"open house|tournament|fun run|run/walk|\b5k\b|\bfair\b|tasting|trivia|bingo|dinner|breakfast|comedy|perform|"
                      r"workshop|\bclass\b|meetup|gathering|celebrat|party|swap|craft|lighting|santa|karaoke|open mic|pop.?up|vendor", re.I)


def extract_when(text, posted):
    """Find an upcoming date (and time) in a post. Returns (datetime, all_day) or None."""
    t = text.lower()
    base = posted.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    day = None
    m = re.search(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m:
        mo, d = MONTHS[m.group(1)[:3]], int(m.group(2))
        try:
            day = base.replace(month=mo, day=d)
        except ValueError:
            day = None
    if not day:
        m = re.search(r"(?<![\d/$])(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?![\d/%])", t)
        if m and 1 <= int(m.group(1)) <= 12:
            try:
                day = base.replace(month=int(m.group(1)), day=int(m.group(2)))
            except ValueError:
                day = None
    if day and day < base - timedelta(days=3):
        try:
            day = day.replace(year=day.year + 1)
        except ValueError:
            return None
    if not day:
        if re.search(r"\b(tonight|today|this evening|this afternoon)\b", t):
            day = base
        elif re.search(r"\btomorrow\b", t):
            day = base + timedelta(days=1)
        else:
            m = re.search(r"\b(this|next|on|every)?\s*(" + "|".join(DAYS) + r")\b", t)
            if m and m.group(1) != "every":
                ahead = (DAYS.index(m.group(2)) - base.weekday()) % 7
                if m.group(1) == "next" and ahead == 0:
                    ahead = 7
                day = base + timedelta(days=ahead)
    if not day or not (0 <= (day - base).days <= 150):
        return None
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(?:-|–|to)\s*\d{1,2}(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.)", t) or \
        re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if 1 <= h <= 12:
            if m.group(3).startswith("p") and h != 12:
                h += 12
            if m.group(3).startswith("a") and h == 12:
                h = 0
            return day.replace(hour=h, minute=mi), False
    return day, True


NEWSY = re.compile(r"\b(AP calls|election results|ballots? (?:count|drop)|arrested|charged with|sentenced|lawsuit|obituary|for sale|looking for (?:a )?(?:job|roommate|apartment))\b", re.I)


def _social_event(text, title, url, posted, network):
    if not EVENTISH.search(text) or NEWSY.search(text):
        return None
    when = extract_when(text, posted)
    if not when:
        return None
    start, allday = when
    if start < NOW - timedelta(hours=2):
        return None
    return {"title": title, "start": start.isoformat(), "allDay": allday, "url": url, "desc": clean(text, 300),
            "venue": "", "address": "", "social": network, "tags": [network]}


def strat_reddit(*subs):
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for sub in subs:
        try:
            root = ET.fromstring(fetch(f"https://www.reddit.com/r/{sub}/new/.rss?limit=100", "application/atom+xml"))
        except Exception as ex:
            print(f"   ! r/{sub}: {ex}")
            continue
        for en in root.findall("a:entry", ns):
            title = clean(en.findtext("a:title", "", ns))
            body = clean(en.findtext("a:content", "", ns))
            body = re.sub(r"submitted by /u/\S+.*$", "", body).strip()
            link = (en.find("a:link", ns).get("href") if en.find("a:link", ns) is not None else "")
            posted, _ = parse_dt(en.findtext("a:published", "", ns) or en.findtext("a:updated", "", ns))
            if not posted or posted < NOW - timedelta(days=45):
                continue
            ev = _social_event(title + ". " + body, title[:140], link, posted, "Reddit")
            if ev:
                ev["address"] = f"r/{sub}"
                out.append(ev)
        time.sleep(8)
    return out


def strat_bluesky(*queries):
    out, seen = [], set()
    for q in queries:
        url = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urllib.parse.urlencode({"q": q, "limit": 100, "sort": "latest"})
        try:
            data = json.loads(fetch(url, "application/json"))
        except Exception as ex:
            print(f"   ! bluesky '{q}': {ex}")
            continue
        for p in data.get("posts", []):
            if p["uri"] in seen:
                continue
            seen.add(p["uri"])
            a = p.get("author", {})
            who = (a.get("handle", "") + " " + (a.get("displayName") or "")).lower()
            if "bot" in who or "nws" in who or "alert" in who:
                continue
            rec = p.get("record", {})
            text = rec.get("text", "")
            posted, _ = parse_dt(rec.get("createdAt"))
            if not posted or posted < NOW - timedelta(days=45) or not find_area(text):
                continue
            first = re.split(r"(?<=[.!?])\s|\n", text.strip())[0]
            link = f"https://bsky.app/profile/{a.get('handle')}/post/{p['uri'].rsplit('/', 1)[-1]}"
            ev = _social_event(text, clean(first, 120), link, posted, "Bluesky")
            if ev:
                ev["address"] = text
                out.append(ev)
        time.sleep(1)
    return out


def strat_crawl(list_url, link_pattern, limit=40, *_):
    """Open a listing page, follow links matching link_pattern, read schema.org Event data on each detail page."""
    page = fetch(list_url, "text/html")
    links = []
    for h in re.findall(r'href=["\']([^"\']+)["\']', page):
        if re.search(link_pattern, h):
            u = urllib.parse.urljoin(list_url, html.unescape(h)).split("#")[0]
            if u not in links:
                links.append(u)
    out = []
    for u in links[:int(limit)]:
        try:
            out += strat_jsonld(u)
        except Exception:
            continue
    return out


def strat_communico(base, *_):
    """Communico (libnet.info) library event calendar."""
    req = json.dumps({"private": False, "date": NOW.strftime("%Y-%m-%d"), "days": 60, "locations": [], "ages": [], "types": []})
    data = json.loads(fetch(f"{base.rstrip('/')}/eeventcaldata?event_type=0&req=" + urllib.parse.quote(req), "application/json"))
    out = []
    for r in data if isinstance(data, list) else data.get("events", []):
        if str(r.get("private", "0")) in ("1", "true", "True"):
            continue
        start = r.get("raw_start_time") or r.get("event_start")
        out.append({"title": clean(r.get("title")), "start": start, "end": r.get("raw_end_time") or r.get("event_end"),
                    "url": f"{base.rstrip('/')}/event/{r.get('id')}", "desc": clean(r.get("description") or r.get("long_description"), 300),
                    "venue": clean(f"{r.get('library') or ''} {r.get('location') or ''}".strip()), "address": clean(r.get("library")),
                    "tags": [clean(t) for t in str(r.get("tags") or "").split(",") if t.strip()][:3]})
    return out


def strat_engage(base, *_):
    """Campus Labs Engage (student event hubs such as GrizHub)."""
    q = urllib.parse.urlencode({"endsAfter": NOW.strftime("%Y-%m-%dT%H:%M:%S%z"), "orderByField": "endsOn", "orderByDirection": "ascending",
                                "status": "Approved", "take": 100, "query": ""})
    data = json.loads(fetch(f"{base.rstrip('/')}/api/discovery/event/search?{q}", "application/json"))
    out = []
    for r in data.get("value", []):
        out.append({"title": clean(r.get("name")), "start": r.get("startsOn"), "end": r.get("endsOn"),
                    "url": f"{base.rstrip('/')}/event/{r.get('id')}", "desc": clean(r.get("description"), 300),
                    "venue": clean(r.get("location")), "address": clean(r.get("location")),
                    "tags": [clean(x) for x in (r.get("categoryNames") or [])][:3]})
    return out


def strat_recurring(*_):
    """Weekly seasonal events (farmers markets, etc.) listed by hand in docs/data/recurring.json."""
    path = os.path.join(DATA, "recurring.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        items = json.load(f).get("recurring", [])
    out, today = [], NOW.date()
    for it in items:
        for i in range(0, 380):
            d = today + timedelta(days=i)
            if d.weekday() not in it["weekdays"] or d.month not in it["months"]:
                continue
            if it.get("from") and d.strftime("%m-%d") < it["from"] and d.month == it["months"][0]:
                continue
            if it.get("until") and d.strftime("%m-%d") > it["until"] and d.month == it["months"][-1]:
                continue
            out.append({"title": it["title"], "start": f"{d.isoformat()}T{it['start']}:00", "end": f"{d.isoformat()}T{it['end']}:00",
                        "venue": it.get("venue", ""), "address": it.get("address", ""), "url": it.get("url"),
                        "desc": it.get("desc", ""), "cost": it.get("cost", ""), "tags": it.get("tags", [])})
    return out


STRATEGIES = {"recurring": strat_recurring, "crawl": strat_crawl, "communico": strat_communico, "engage": strat_engage, "reddit": strat_reddit, "bluesky": strat_bluesky, "libcal": strat_libcal, "chambermaster": strat_chambermaster, "tribe": strat_tribe, "ical": strat_ical, "jsonld": strat_jsonld, "discover": strat_discover}


# ---------------------------------------------------------------- normalize
def norm_title(t):
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    t = re.sub(r"\b(the|a|an|at|and|with|w|live|presents|feat|featuring)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def finalize(raw, src):
    s, allday = parse_dt(raw.get("start"))
    if not s or not raw.get("title"):
        return None
    if src.get("exclude") and re.search(src["exclude"], raw["title"] + " | " + " ".join(raw.get("tags", [])), re.I):
        return None
    e_dt, _ = parse_dt(raw.get("end"))
    if not e_dt or e_dt < s:
        e_dt = s if allday else s + timedelta(hours=2)
    if e_dt < NOW - timedelta(hours=1) or s > HORIZON:
        return None
    allday = allday or bool(raw.get("allDay"))
    venue, address = raw.get("venue", ""), raw.get("address", "")
    area = find_area(venue, address)
    if src.get("aggregator"):
        if not area:
            return None
    else:
        if not area and far_away(venue, address, raw["title"], raw.get("desc", "")):
            return None
        area = area or find_area(raw["title"], raw.get("desc", "")) or src.get("town")
    e = {
        "title": raw["title"][:160], "start": s.isoformat(), "end": e_dt.isoformat(), "allDay": allday,
        "venue": venue[:120], "address": address[:200], "town": area, "url": raw.get("url") or src.get("site"),
        "desc": raw.get("desc", ""), "cost": (raw.get("cost") or "")[:60], "image": raw.get("image"),
        "ticketUrl": raw.get("ticketUrl"), "tags": [t for t in raw.get("tags", []) if t][:5],
        "sources": [src["name"]], "_concerts": bool(src.get("concerts")),
        "social": raw.get("social"),
    }
    categorize(e)
    del e["_concerts"]
    if src.get("bigTitles"):   # a source can say which of its events are Plan Ahead material
        e["big"] = bool(re.search(src["bigTitles"], e["title"], re.I)) and not e["free"]
    if e.get("social"):
        e["address"] = ""
    else:
        e.pop("social", None)
    base = re.split(r"\s@\s?|\s+[-–|]\s+(?=[A-Z][a-z]+ (?:Performing|Center|Theater|Theatre|Amphitheat))", e["title"])[0]
    if venue:
        vw = re.escape(venue.split()[0])
        base = re.split(r"\s+at\s+(?:the\s+)?" + vw, base, flags=re.I)[0]
    key = norm_title(base) + "|" + s.date().isoformat()
    e["id"] = hashlib.sha1(key.encode()).hexdigest()[:12]
    return e


def merge(events):
    by = {}
    for e in events:
        if e["id"] in by:
            a = by[e["id"]]
            for k in ("venue", "address", "desc", "cost", "image", "ticketUrl", "town"):
                if not a.get(k) and e.get(k):
                    a[k] = e[k]
            a["sources"] = sorted(set(a["sources"] + e["sources"]))
            a["big"] = a["big"] or e["big"]
            a["ticketed"] = a["ticketed"] or e["ticketed"]
            a["cats"] = list(dict.fromkeys(a["cats"] + e["cats"]))[:3]
        else:
            by[e["id"]] = e
    return list(by.values())


def load_tips():
    path = os.path.join(DATA, "tips.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("tips", [])


# ---------------------------------------------------------------- outputs
def ics_escape(s):
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def write_ics(events, path):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//wenatchee-activities//Plan Ahead//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:" + (REGION.get("name") or "Wenatchee Area") + " – Plan Ahead", "X-WR-TIMEZONE:" + str(TZ), "REFRESH-INTERVAL;VALUE=DURATION:PT24H"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for e in events:
        s, _ = parse_dt(e["start"])
        en, _ = parse_dt(e["end"])
        if e["allDay"]:
            ds = f"DTSTART;VALUE=DATE:{s:%Y%m%d}"
            de = f"DTEND;VALUE=DATE:{(en + timedelta(days=1)):%Y%m%d}"
        else:
            ds = "DTSTART:" + s.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            de = "DTEND:" + en.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines += ["BEGIN:VEVENT", f"UID:{e['id']}@wenatchee-activities", f"DTSTAMP:{stamp}", ds, de,
                  "SUMMARY:" + ics_escape(e["title"]),
                  "LOCATION:" + ics_escape(", ".join(x for x in (e["venue"], e["town"]) if x)),
                  "DESCRIPTION:" + ics_escape(f"{e.get('cost') or ''} {e.get('desc') or ''}\n{e.get('ticketUrl') or e.get('url') or ''}".strip()),
                  "URL:" + (e.get("ticketUrl") or e.get("url") or ""),
                  "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Get tickets: " + ics_escape(e["title"]), "TRIGGER:-P21D", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    with open(path, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")


def main():
    with open(os.path.join(DATA, "sources.json")) as f:
        sources = [s for s in json.load(f)["sources"] if s.get("enabled", True)]
    prev_path = os.path.join(DATA, "events.json")
    prev = {}
    if os.path.exists(prev_path):
        try:
            with open(prev_path) as f:
                prev = {e["id"]: e for e in json.load(f).get("events", [])}
        except Exception:
            prev = {}

    all_events, health = [], []
    for src in sources:
        t0, status, err, used, got = time.time(), "error", "", None, []
        for strat in src["strategies"]:
            name, args = strat[0], strat[1:]
            try:
                raw = STRATEGIES[name](*args)
                got = [e for e in (finalize(r, src) for r in raw) if e]
                used = name
                if raw:
                    status = "ok"
                    break
                status, err = "empty", f"{name}: no events found"
            except Exception as ex:
                err = f"{name}: {type(ex).__name__}: {str(ex)[:120]}"
        print(f"{src['name']:<36} {status:<6} {len(got):>4}  {used or ''} {err if status != 'ok' else ''}")
        health.append({"name": src["name"], "site": src.get("site"), "status": status, "count": len(got),
                       "method": used, "error": err if status != "ok" else "", "seconds": round(time.time() - t0, 1)})
        all_events += got

    tip_src = {"name": "Community tip", "town": None}
    tips = [e for e in (finalize(t, tip_src) for t in load_tips()) if e]
    for e in tips:
        e["tip"] = True
    health.append({"name": "Community tips", "site": None, "status": "ok", "count": len(tips), "method": "tips.json", "error": ""})
    all_events += tips

    events = merge(all_events)
    # Recurring series (classes, weekly bingo, daily demos, a hockey season): not "plan ahead" material,
    # and keep only the next 40 dates so one series can't flood the list.
    events.sort(key=lambda e: e["start"])
    series = {}
    for e in events:
        k = norm_title(re.split(r"\s@\s|\bat\b", e["title"])[0]) + "|" + (e["town"] or "")
        series.setdefault(k, []).append(e)
    keep = []
    for k, lst in series.items():
        if len(lst) > 3:
            for e in lst:
                e["big"] = False
                e["repeats"] = len(lst)
        keep += lst[:40]
    events = keep
    stamp = NOW.isoformat()
    first_run = not prev
    new_big = []
    for e in events:
        old = prev.get(e["id"])
        e["firstSeen"] = old.get("firstSeen", stamp) if old else stamp
        if not old and not first_run and e["big"]:
            new_big.append(e)
    events.sort(key=lambda e: (e["start"], e["title"]))

    # Refuse to wipe the site if every source failed (e.g. a network hiccup)
    if not any(h["count"] for h in health if h["name"] != "Community tips") and prev:
        print("All sources failed; keeping previous data.", file=sys.stderr)
        sys.exit(0)

    with open(prev_path, "w") as f:
        json.dump({"updated": stamp, "areas": REGION.get("displayOrder") or AREA_NAMES, "region": {k: REGION.get(k) for k in ("name", "tagline", "repo", "tz")}, "sources": health, "events": events}, f, separators=(",", ":"))
    big = [e for e in events if e["big"]]
    write_ics(big, os.path.join(DATA, "plan-ahead.ics"))
    with open(os.path.join(DATA, "new-big.json"), "w") as f:
        json.dump(new_big, f, indent=1)
    print(f"\n{len(events)} events ({len(big)} plan-ahead, {len(new_big)} newly announced) from "
          f"{sum(1 for h in health if h['status'] == 'ok')} working sources")


if __name__ == "__main__":
    main()
