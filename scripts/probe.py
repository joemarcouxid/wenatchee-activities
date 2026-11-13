#!/usr/bin/env python3
"""Diagnostic: show what each candidate calendar URL offers (run via the 'Probe sources' workflow)."""
import json, re, sys, os, urllib.request, gzip
sys.path.insert(0, os.path.dirname(__file__))
import collect as c
UAS = {"ours": c.UA, "plain": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
KEYS = ["trumba","localist","simpleview","growthzone","chambermaster","cloudflare","wix","squarespace","showare","ticketmaster","etix","tribe-events","libcal","librarycalendar","communico","assabet","evanced","bibliocommons","civicplus","eventbrite","ajax","api/"]
def get(u, ua):
    req = urllib.request.Request(u, headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
        return r.status, raw.decode("utf-8", "replace")
URLS = sys.argv[1:] or open(os.path.join(os.path.dirname(__file__), "probe-urls.txt")).read().split()
for u in URLS:
    for name, ua in UAS.items():
        try:
            st, body = get(u, ua)
        except Exception as ex:
            print(f"XX[{name}] {u} -> {type(ex).__name__}: {str(ex)[:90]}"); continue
        acc = []
        p = c._LD()
        try: p.feed(body)
        except Exception: pass
        for b in p.blocks:
            try: c._walk_ld(json.loads(b.strip().rstrip(";")), acc)
            except Exception: pass
        kws = [k for k in KEYS if k in body.lower()]
        print(f"OK[{name}] {u} st={st} len={len(body)} ld={len(acc)} vevent={body.count('BEGIN:VEVENT')} kw={kws}")
        if u.endswith("json") or "wp-json" in u or "api" in u:
            print("   body:", body[:600].replace("\n"," "))
        else:
            for x in sorted(set(re.findall(r'(?:src|href|data-[a-z-]+)="([^"]*(?:api|json|feed|ical|ics|calendar|event)[^"]*)"', body, re.I)))[:14]:
                print("   ref:", x[:170])
        break
