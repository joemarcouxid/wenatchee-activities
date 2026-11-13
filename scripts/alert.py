#!/usr/bin/env python3
"""Print a Markdown summary of newly announced concerts / big events (data/new-big.json), or nothing."""
import json, os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "data", "new-big.json")) as f:
    new = json.load(f)
new = [e for e in new if datetime.fromisoformat(e["start"]) > datetime.now(datetime.fromisoformat(e["start"]).tzinfo)]
if new:
    new.sort(key=lambda e: e["start"])
    print("New concerts and big events just showed up. Tickets may already be on sale:\n")
    for e in new[:40]:
        d = datetime.fromisoformat(e["start"])
        when = d.strftime("%a %b %-d, %Y") + ("" if e["allDay"] else d.strftime(" · %-I:%M %p"))
        link = e.get("ticketUrl") or e.get("url") or ""
        where = ", ".join(x for x in (e.get("venue"), e.get("town")) if x)
        cost = f" · {e['cost']}" if e.get("cost") else ""
        print(f"- **[{e['title']}]({link})**: {when} · {where}{cost}")
    if len(new) > 40:
        print(f"\n…and {len(new) - 40} more. See the Plan Ahead tab.")
    print("\nClose this issue once you've seen it.")
