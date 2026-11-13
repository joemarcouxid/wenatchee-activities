#!/usr/bin/env python3
"""Diagnostic: show what each candidate calendar URL offers (run via the 'Probe sources' workflow)."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import collect as c
URLS = sys.argv[1:] or open(os.path.join(os.path.dirname(__file__), "probe-urls.txt")).read().split()
for u in URLS:
    try:
        body = c.fetch(u)
    except Exception as ex:
        print(f"XX {u} -> {type(ex).__name__}: {str(ex)[:100]}"); continue
    p = c._LD(); 
    try: p.feed(body)
    except Exception: pass
    acc = []
    for b in p.blocks:
        try: c._walk_ld(json.loads(b.strip().rstrip(";")), acc)
        except Exception: pass
    feeds = sorted({h for h in p.links if re.search(r"ical|\.ics|webcal|wp-json|rss|feed|/api/", h, re.I)})[:12]
    evlinks = sorted({h for h in p.links if re.search(r"event|calendar|show", h, re.I)})[:15]
    tribe = "tribe-events" in body or "wp-json/tribe" in body
    print(f"OK {u} len={len(body)} ldEvents={len(acc)} tribe={tribe} ics={body.count('BEGIN:VEVENT')}")
    if acc: print("   first:", acc[0].get("name"), acc[0].get("startDate"))
    for f in feeds: print("   feed:", f)
    for f in evlinks: print("   link:", f)
    m = re.findall(r'(https?://[^"\' ]*(?:api|json)[^"\' ]*)', body)[:6]
    for x in m: print("   api?:", x[:160])
