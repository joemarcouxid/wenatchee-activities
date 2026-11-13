import re, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import collect as c
b = c.fetch("https://ncwlibraries.libcal.com/ajax/calendar/list?c=-1&date=0000-00-00&perpage=48&page=1&audience=&cats=&camps=&inc=0")
d = json.loads(b); r = d["results"][3]
print("LIBCAL keys:", list(r.keys())); print(json.dumps({k: (v if len(str(v)) < 150 else str(v)[:150]) for k, v in r.items()}, indent=0)[:2500])
print("LIBCAL campuses:", sorted({x.get("campus") or x.get("location") or "" for x in d["results"]}))
b = c.fetch("https://www.calendarwiz.com/cwapi.php?crd=visitwenatchee&view=l")
print("CW len", len(b)); print(b[:2500])
b = c.fetch("https://events.timely.fun/api/calendars/54735125/export?format=ics")
i = b.find("BEGIN:VEVENT"); print("TIMELY", b[i:i+1800])
locs = re.findall(r"\nLOCATION:([^\r\n]*)", b); print("TIMELY locs sample:", locs[:25])
