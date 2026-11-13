#!/usr/bin/env python3
"""Turn a '[Tip]' GitHub issue (from the Submit-a-tip form) into an entry in data/tips.json.
Reads the issue body from the ISSUE_BODY environment variable."""
import json, os, re, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "tips.json")


def fields(body):
    out, key = {}, None
    for line in body.splitlines():
        m = re.match(r"^###\s+(.*)", line)
        if m:
            key = m.group(1).strip().lower()
            out[key] = ""
        elif key is not None:
            out[key] += line + "\n"
    return {k: ("" if v.strip() == "_No response_" else v.strip()) for k, v in out.items()}


def get(f, *names):
    for n in names:
        for k, v in f.items():
            if k.startswith(n):
                return v
    return ""


def to_time(s):
    s = s.strip().lower().replace(".", "")
    if not s:
        return None
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime("%H:%M")
        except ValueError:
            pass
    return None


def main():
    f = fields(os.environ.get("ISSUE_BODY", ""))
    title = get(f, "what")
    day = get(f, "date")
    try:
        day = datetime.strptime(day.strip(), "%Y-%m-%d").date()
    except ValueError:
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m/%d"):
            try:
                d = datetime.strptime(day.strip(), fmt)
                if fmt == "%m/%d":
                    now = datetime.now()
                    d = d.replace(year=now.year if d.month >= now.month else now.year + 1)
                day = d.date()
                break
            except ValueError:
                continue
    if not title or not hasattr(day, "isoformat"):
        print("Could not read the event name or date (use YYYY-MM-DD or MM/DD/YYYY).", file=sys.stderr)
        sys.exit(1)
    st, en = to_time(get(f, "start")), to_time(get(f, "end"))
    town, venue = get(f, "town"), get(f, "where")
    tip = {
        "title": title,
        "start": f"{day.isoformat()}T{st}:00" if st else day.isoformat(),
        "end": f"{day.isoformat()}T{en}:00" if (st and en) else (None if st else day.isoformat()),
        "allDay": not st,
        "venue": venue, "address": f"{venue}, {town}, WA",
        "url": get(f, "link") or os.environ.get("ISSUE_URL", ""),
        "desc": get(f, "details"), "cost": get(f, "cost"),
        "tags": [t for t in [get(f, "kind")] if t and t != "Other"],
        "issue": os.environ.get("ISSUE_URL", ""),
    }
    data = {"tips": []}
    if os.path.exists(PATH):
        with open(PATH) as fh:
            data = json.load(fh)
    data["tips"].append(tip)
    with open(PATH, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"Added tip: {title} on {day}")


if __name__ == "__main__":
    main()
