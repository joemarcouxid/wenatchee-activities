import re, sys, os, time, json, base64, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
import collect as c
def show(u, n=700):
    try:
        b = c.fetch(u); print(f"OK {u} len={len(b)} vevent={b.count('BEGIN:VEVENT')}\n   {b[:n]!r}"); return b
    except Exception as ex:
        print(f"XX {u} -> {ex}"); return ""
b = show("https://towntoyotacenter.com/events-tickets/calendars/", 0)
for src in re.findall(r'calendar\.google\.com/calendar/embed\?([^"]+)"', b):
    q = urllib.parse.parse_qs(html.unescape(src) if False else src.replace("&#038;","&"))
    for s in q.get("src", []):
        try: cid = base64.b64decode(s + "=" * (-len(s) % 4)).decode()
        except Exception: cid = s
        print("  gcal:", cid)
        show(f"https://calendar.google.com/calendar/ical/{urllib.parse.quote(cid)}/public/basic.ics", 300)
b = show("https://www.calendarwiz.com/eventboard/?crd=visitwenatchee", 0)
for m in re.findall(r'(?:url|href|src)\s*[:=]\s*["\']([^"\']*(?:php|ajax|json|api)[^"\']*)', b)[:15]: print("  cw:", m)
show("https://ncwlibraries.libcal.com/ical_subscribe.php?src=p&cid=-1", 300)
show("https://ncwlibraries.libcal.com/ajax/calendar/list?c=-1&date=0000-00-00&perpage=5&page=1&audience=&cats=&camps=&inc=0", 900)
show("https://ncwlibraries.libcal.com/rss.php?iid=6523&m=month&cid=-1", 500)
now = int(time.time())
for u in ["https://events.timely.fun/api/calendars/54735125/events?start_date_utc=%d&per_page=5&page=1" % now,
          "https://timelyapp.time.ly/api/calendars/54735125/events?start_date_utc=%d&per_page=5&page=1" % now,
          "https://events.timely.fun/api/calendars/54735125/export?format=ics",
          "https://events.timely.fun/bm30tqng/export/ics"]:
    show(u, 600)
time.sleep(20)
show("https://www.wenatcheeworld.com/calendar/search/?f=rss&t=event&c=calendar*&d1=now&unrolled=1&l=3&s=start_time&sd=asc", 900)
show("https://www.missionridge.com/wp-json/tribe/events/v1/categories?per_page=50", 1200)
