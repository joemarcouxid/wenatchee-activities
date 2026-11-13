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
TZ = ZoneInfo("America/Los_Angeles")
NOW = datetime.now(TZ)
HORIZON = NOW + timedelta(days=400)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36 wenatchee-activities/1.0 (+https://github.com/joemarcouxid/wenatchee-activities)")

# ---------------------------------------------------------------- geography
# (area shown in the app, words that identify it, ZIP codes)
AREAS = [
    ("Leavenworth", ["lake wenatchee", "leavenworth", "plain, wa", "plain wa", "icicle road", "front street, leavenworth"], ["98826"]),
    ("East Wenatchee", ["east wenatchee", "rock island", "orondo"], ["98802", "98850", "98843"]),
    ("Wenatchee", ["wenatchee", "malaga", "mission ridge", "sunnyslope"], ["98801", "98807", "98828"]),
    ("Cashmere", ["cashmere", "peshastin", "dryden", "monitor, wa"], ["98815", "98847", "98821", "98836"]),
    ("Entiat", ["entiat", "ardenvoir"], ["98822", "98811"]),
    ("Chelan", ["chelan", "manson", "stehekin"], ["98816", "98831", "98817", "98852"]),
    ("Quincy", ["quincy", "george, wa", "george wa", "gorge amphitheat", "the gorge", "crescent bar", "cave b", "sunland estates"], ["98848", "98824"]),
]
AREA_NAMES = [a[0] for a in AREAS]
# Places that contain our town names but are elsewhere
NOT_HERE = ["quincy, ma", "quincy, il", "quincy, ca", "quincy, fl", "chelan county pud", "seattle", "spokane", "yakima",
            "ellensburg", "moses lake", "ephrata", "twisp", "winthrop", "omak", "tacoma", "bellevue", "everett", "kennewick"]


def find_area(*texts):
    t = " ".join(x for x in texts if x).lower()
    if not t:
        return None
    for name, _, zips in AREAS:
        for z in zips:
            if re.search(r"\b%s\b" % z, t):
                return name
    for name, words, _ in AREAS:
        for w in words:
            if w in t:
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
              "craft", "workshop", "glass", "paint", "book signing", "poetry", "musical", "play ", "improv", "author", "pottery", "photography"]),
    ("markets", ["market", "bazaar", "fair", "farmers", "vendor", "swap", "flea", "holiday shopping", "artisan"]),
    ("festivals", ["festival", "fest", "parade", "celebration", "oktoberfest", "christmas", "village of lights", "holiday", "karneval",
                   "fireworks", "tree lighting", "winterfest", "4th of july", "fourth of july", "blossom", "salmon fest", "halloween", "new year"]),
]
BIG_VENUES = ["gorge amphitheat", "the gorge", "town toyota center", "numerica", "performing arts center", "festhalle",
              "snowy owl theater", "icicle creek center", "convention center", "cave b", "leavenworth summer theater", "ski hill amphitheater"]
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
    e["big"] = bool(big_venue or (not e["free"] and (e.get("_concerts") or (e["ticketed"] and showy))))


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
        cur = None
        for line in unfold_ics(fetch(url, "text/calendar")):
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


STRATEGIES = {"tribe": strat_tribe, "ical": strat_ical, "jsonld": strat_jsonld, "discover": strat_discover}


# ---------------------------------------------------------------- normalize
def norm_title(t):
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    t = re.sub(r"\b(the|a|an|at|and|with|w|live|presents|feat|featuring)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def finalize(raw, src):
    s, allday = parse_dt(raw.get("start"))
    if not s or not raw.get("title"):
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
        if not area and far_away(venue, address):
            return None
        area = area or find_area(raw["title"]) or src.get("town")
    e = {
        "title": raw["title"][:160], "start": s.isoformat(), "end": e_dt.isoformat(), "allDay": allday,
        "venue": venue[:120], "address": address[:200], "town": area, "url": raw.get("url") or src.get("site"),
        "desc": raw.get("desc", ""), "cost": (raw.get("cost") or "")[:60], "image": raw.get("image"),
        "ticketUrl": raw.get("ticketUrl"), "tags": [t for t in raw.get("tags", []) if t][:5],
        "sources": [src["name"]], "_concerts": bool(src.get("concerts")),
    }
    categorize(e)
    del e["_concerts"]
    key = norm_title(e["title"]) + "|" + s.date().isoformat()
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
             "X-WR-CALNAME:Wenatchee Area – Plan Ahead", "X-WR-TIMEZONE:America/Los_Angeles", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
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
        json.dump({"updated": stamp, "areas": AREA_NAMES, "sources": health, "events": events}, f, separators=(",", ":"))
    big = [e for e in events if e["big"]]
    write_ics(big, os.path.join(DATA, "plan-ahead.ics"))
    with open(os.path.join(DATA, "new-big.json"), "w") as f:
        json.dump(new_big, f, indent=1)
    print(f"\n{len(events)} events ({len(big)} plan-ahead, {len(new_big)} newly announced) from "
          f"{sum(1 for h in health if h['status'] == 'ok')} working sources")


if __name__ == "__main__":
    main()
