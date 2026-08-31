# Prospect Heat Map

A single-file field-prospecting heat map. No build step, no accounts, no API keys.
Open `index.html` in any browser (works on your phone too).

> **Working on this project?** Read [HANDOFF.md](HANDOFF.md) first — architecture,
> known landmines, and what's unfinished.

## What it does

- Plots prospects on a map with a **heat layer** on top.
- **Heat mode switcher** — flip what "hot" means:
  - **Density** — where the most targets are.
  - **Fit score** — where the best-fit prospects cluster.
  - **Pipeline $** — where the money potential is.
  - **Coverage gaps** — untapped areas glow, worked areas fade (great once you're in the field).
- **New-opening alerts** — restaurants opening soon / recently opened show as **pulsing markers**,
  and a **rotating alert toast** (top-right) surfaces them one at a time. Tap a toast to fly to it.
  Use the **"New openings only"** toggle to filter the whole map down to them.
- **Filters** — by category and by status (new / contacted / customer).
- **Pins** — tap any dot for the prospect's details. Dot color = status.

## New-opening alerts: going live

Right now openings are mock-flagged in `makeMockData()`. For a real live feed, the strongest
signals for a restaurant opening in Westchester (best → backup):

1. **NY State Liquor Authority** new on-premises license applications (public data).
2. **Westchester County Health Dept** new food-service permit filings.
3. **Google Places API** (`business_status`) + **Yelp** "new business" listings.

The plan: a small scheduled job polls these, geocodes new hits, and appends them to the
prospect list with an `opening` flag — the pulsing markers and toast already handle the rest.

## Real vs. placeholder data

The venues are **real** — 1,006 restaurants, cafes, bars, fast food, and bakeries across
Westchester, pulled from OpenStreetMap. Real fields: **name, category, cuisine, street, lat/lng**.

The only simulated parts (because you haven't prospected yet) are:

- **status** — every venue starts as `new` (untouched). This becomes real as you log visits.
- **fitScore / monthlyValue** — rough *estimates* so the Fit and Pipeline heat modes have
  something to show. Replace with your real assessments over time.
## New-opening alerts are REAL

Openings come from the **NY State Liquor Authority "Current SLA Pending Licenses"** dataset
(data.ny.gov) — restaurants that have filed for a liquor license but aren't open yet, the
earliest public signal of a new restaurant. `openings_feed.py` pulls Westchester food-service
filings, batch-geocodes the addresses via the free US Census geocoder, and writes `openings.js`.

Each opening carries its real **license stage** (Conditionally Approved > Under Review >
IntakeComplete) so the hottest, closest-to-opening leads sort first.

**Refresh anytime:** `python3 openings_feed.py`  (re-pulls and re-geocodes; run it weekly to
catch new filings). Only placeholder part of an opening is the fit/$ estimate.

## Refreshing the venue list

`build_data.py` reads `overpass_raw.json` and writes `restaurants.js`. To re-pull from
OpenStreetMap (e.g. wider area or updated venues), re-run the Overpass query into
`overpass_raw.json`, then `python3 build_data.py`.

## Making it yours (all in `index.html`)

Everything you'll touch is at the top of the `<script>` block:

1. **`CONFIG.center`** — set to your territory's lat/lng and it recenters.
2. **`CONFIG.categories`** — rename to your actual verticals.
3. **`MODES`** — add or tweak heat lenses (each is just a function returning a 0–1 weight).

## Going live with real data

Replace `makeMockData()` with your real list. Each prospect just needs:

```js
{ id, name, category, lat, lng, fitScore, monthlyValue, status }
```

When you're ready, the cleanest path is to keep your leads in a spreadsheet, export CSV,
and load it here — ping me and I'll wire up CSV import + address→lat/lng geocoding so you
can drop in a list without hand-coding coordinates.

## The researched overlay (curated.js)

That "going live" path now exists: `curated.js` carries the **96 hand-researched
prospects** from `~/Documents/CT-Westchester Prospecting List.xlsx` — verified
open, geocoded, with phone, contact, segment, a human 1–5 fit rating, and a
one-line "why it fits". At load they either upgrade the matching OSM venue in
place (20 do) or appear as their own pins (76 — venues OSM was missing, mostly
hotel restaurants, bakeries, caterers). Blue-ringed pins are researched; the
**📋 Researched list only** toggle filters down to them, and their popups show
the contact intel. The overlay also extends coverage into **Fairfield County,
CT** (Greenwich → Fairfield), so pan east.

If the spreadsheet changes, regenerate rather than hand-edit — the generator
lives with the spreadsheet workflow (ask Claude to "rebuild curated.js from the
prospecting list").
