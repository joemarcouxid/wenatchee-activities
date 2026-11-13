import sys, os, json, re, urllib.parse, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(__file__))
import collect as c
ns = {"a": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(c.fetch("https://www.reddit.com/r/Wenatchee/new/.rss?limit=100"))
ents = root.findall("a:entry", ns); print("REDDIT entries", len(ents))
for en in ents:
    t = c.clean(en.findtext("a:title", "", ns)); b = c.clean(en.findtext("a:content", "", ns))[:200]
    posted, _ = c.parse_dt(en.findtext("a:published", "", ns))
    print(" ", posted.date() if posted else "?", "| ev" if c.EVENTISH.search(t + b) else "|   ", "|", c.extract_when(t + ". " + b, posted) and "DATE" or "    ", "|", t[:80])
for q in ["wenatchee", "leavenworth wa", "lake chelan"]:
    d = json.loads(c.fetch("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urllib.parse.urlencode({"q": q, "limit": 100, "sort": "latest"})))
    ps = d.get("posts", []); print("BSKY", q, len(ps))
    for p in ps[:40]:
        t = p["record"]["text"].replace("\n", " "); posted, _ = c.parse_dt(p["record"]["createdAt"])
        if c.EVENTISH.search(t): print("  ", posted.date(), "| DATE" if c.extract_when(t, posted) else "|     ", "| area" if c.find_area(t) else "|     ", "|", p["author"]["handle"][:20], "|", t[:110])
