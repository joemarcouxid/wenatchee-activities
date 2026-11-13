import re, sys, os, json, collections
sys.path.insert(0, os.path.dirname(__file__))
import collect as c
b = json.loads(c.fetch("https://www.calendarwiz.com/cwapi.php?crd=visitwenatchee&view=l"))
print("CW top keys:", list(b.keys()))
for k, v in b.items():
    if isinstance(v, list) and v and isinstance(v[0], dict): print("CW list", k, len(v), json.dumps(v[0])[:900])
    if isinstance(v, dict) and k not in ("status", "settings"): print("CW dict", k, json.dumps(v)[:900])
b = c.fetch("https://events.timely.fun/api/calendars/54735125/export?format=ics")
lines = c.unfold_ics(b)
props = collections.Counter(l.split(":")[0].split(";")[0] for l in lines if ":" in l)
print("TIMELY props:", props.most_common(40))
evs = c.strat_ical("https://events.timely.fun/api/calendars/54735125/export?format=ics")
print("TIMELY parsed", len(evs))
up = [e for e in evs if c.parse_dt(e["start"])[0] and c.parse_dt(e["start"])[0] > c.NOW]
print("TIMELY upcoming", len(up))
for e in up[:25]: print("  ", e["start"][:16], e["title"][:60], "| loc:", e.get("address","")[:60], "| area:", c.find_area(e.get("venue"), e.get("address"), e["title"], e.get("desc")))
