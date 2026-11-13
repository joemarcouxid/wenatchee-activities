# ⛰️ Valley Happenings: wenatchee-activities

One place to see what's going on in the Wenatchee Valley: **Wenatchee, East Wenatchee, Cashmere, Leavenworth, Entiat, Chelan/Manson and Quincy/George (the Gorge)**.

**Live site:** https://joemarcouxid.github.io/wenatchee-activities/

## What it does
- **Today · This Weekend · Next 7 Days · This Month · This Year** tabs, with a count on each
- **🎟 Plan Ahead**: concerts, shows and big ticketed events a week or more out, with **🆕 newly announced** flags so you can get tickets early
- **⭐ My List**: tap ☆ on anything to save it on your phone
- Filter by town and by kind (Food & Drink, Music, Family, Outdoors, Races & Sports, Arts & Shows, Markets, Festivals, Community), or search ("food truck", "trivia", "kids")
- **🔄 Refresh** loads the latest scan; **Scan now** runs a fresh scan on GitHub
- **📅 Add** puts any event in your phone calendar (big events get reminders 2 weeks and 1 day before)
- **＋ Add a tip** for food truck posts, flyers and Facebook events the scanner can't see

## Heads-up for tickets (pick one or both)
1. **Phone calendar:** on the Plan Ahead tab, tap **Subscribe on this phone**. Concerts and big events show up in your calendar automatically, with a reminder 3 weeks out. Feed: `webcal://joemarcouxid.github.io/wenatchee-activities/data/plan-ahead.ics`
2. **Email / GitHub app alert:** when a scan finds a newly announced concert or big event, it opens an issue titled "🎟 New events announced". Make sure you're **Watching** this repo (Watch → All Activity, or Custom → Issues) and GitHub will email you or push to the GitHub mobile app.

## How it works
```
once a day ─► GitHub Actions runs scripts/collect.py
                   ├─ reads ~20 public calendars listed in docs/data/sources.json
                   ├─ removes duplicates, tags each event by town and kind
                   ├─ writes docs/data/events.json and plan-ahead.ics
                   └─ opens an alert issue for newly announced big events
GitHub Pages ─► docs/index.html shows the events
```
Sources include the Leavenworth, Lake Chelan, Wenatchee Valley, Cashmere, Entiat and Quincy chambers; Visit Wenatchee; Wenatchee Outdoors; WSU Extension; Numerica PAC; Town Toyota Center; WVC; Pybus Market; NCW Libraries; Wenatchee River Institute; Icicle Creek Center for the Arts; plus AllEvents (which includes many public Facebook events), HappeningNext and Songkick (including the Gorge), plus event posts on Reddit (r/Wenatchee and nearby) and Bluesky that mention a date, all filtered to this area.

The **Sources & status** link at the bottom of the site shows which sources are working and how many events each one found. Some sites block automated readers or change their layout. To add or fix one, edit `docs/data/sources.json` (the `_help` line at the top explains the format).

## Food trucks and small stuff
Most food trucks only post on Facebook or Instagram, which can't be read automatically. The app catches the ones that show up on brewery, cidery, chamber and Eventbrite calendars. For everything else, tap **＋ Add a tip**. It opens a short form; when you submit it, the event shows up on the site in a minute or two. Only tips from you or collaborators you add are published.

## One-time setup
1. **Settings → Pages →** Source: *Deploy from a branch*, Branch: `main` / `/docs` (already set) → Save.
2. **Actions → "Scan for events" → Run workflow** to do the first scan right away. After that it runs on its own once a day, early in the morning.
3. **Watch** the repo (top right) so new-event alerts reach you.
