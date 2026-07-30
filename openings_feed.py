#!/usr/bin/env python3
"""Build openings.js — REAL new-restaurant openings for Westchester.

Two NY State Liquor Authority sources (data.ny.gov), both free / no API key:
  1. "Current SLA Pending Licenses"  -> OPENING SOON (filed, not open yet).
     Addresses geocoded via the free US Census geocoder.
  2. "Current Liquor Authority Active Licenses" -> JUST OPENED (license issued
     in the last RECENT_DAYS). Already ships with coordinates, no geocoding.

Re-run any time to refresh: python3 openings_feed.py
"""
import sys, json, time, hashlib, subprocess, urllib.request, urllib.parse
from datetime import datetime, timedelta

COUNTY = "Westchester"
SLA_PENDING_URL = ("https://data.ny.gov/resource/f8i8-k2gm.json"
                   f"?premises_county={COUNTY}&$limit=2000")
SLA_ACTIVE_RES = "https://data.ny.gov/resource/9s3h-dpkz.json"
BATCH_GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

RECENT_DAYS = 60  # "just opened" = license issued within this many days

# SLA "description" values we treat as prospects (food service we'd service).
KEEP = {"Restaurant", "Tavern", "Catering Establishment", "Summer Restaurant"}

# Map SLA status -> how close to opening (higher = sooner). Just for sorting/labeling.
STAGE_RANK = {"Conditionally Approved": 3, "Under Review": 2,
              "IntakeComplete": 1, "Reconsideration": 1}

# Corporate-name suffixes to strip so "SOUTHERN TABLE INC" reads "Southern Table".
SUFFIXES = (" INC", " LLC", " CORP", " LTD", " CO", " LP", " INC.", " CORP.", " L L C")

def nice_name(raw):
    n = (raw or "").strip()
    up = n.upper()
    for s in SUFFIXES:
        if up.endswith(s):
            n = n[: len(n) - len(s)]
            up = n.upper()
    n = n.strip(" ,")
    return n.title() if n.isupper() or n.islower() else n

def fetch(url):
    req = urllib.request.Request(url, headers={
        "Accept-Encoding": "gzip",
        "User-Agent": "westchester-prospect-map/1.0 (personal prospecting tool)",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return json.loads(raw)

def clean(s):
    return (s or "").replace(",", " ").replace('"', "").strip()

def geocode_batch(rows):
    """rows: list of (id, street, city, zip). Returns {id: (lat, lng)} via one
    Census batch request (curl handles the multipart POST reliably)."""
    csv_lines = [f"{i},{clean(st)},{clean(ci)},NY,{clean(z)}" for (i, st, ci, z) in rows]
    with open("/tmp/sla_addr.csv", "w") as f:
        f.write("\n".join(csv_lines) + "\n")
    out = subprocess.run([
        "curl", "-s", "-m", "120", "--compressed",
        "--form", "addressFile=@/tmp/sla_addr.csv",
        "--form", "benchmark=Public_AR_Current",
        BATCH_GEOCODER,
    ], capture_output=True, text=True).stdout

    coords = {}
    import csv as _csv, io
    for parts in _csv.reader(io.StringIO(out)):
        if len(parts) >= 6 and parts[2] == "Match" and parts[5]:
            lng, lat = parts[5].split(",")
            coords[parts[0]] = (round(float(lat), 6), round(float(lng), 6))
    return coords

def det(s, salt=""):
    return int(hashlib.md5((salt + s).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF

print(f"Fetching pending SLA licenses for {COUNTY}…")
rows = fetch(SLA_PENDING_URL)
prospects = [r for r in rows if r.get("description") in KEEP]
print(f"  {len(rows)} pending total, {len(prospects)} food-service prospects")

# Geocode every address in a single batch request.
geo_rows = []
for idx, r in enumerate(prospects):
    addr = (r.get("actual_address_of_premises") or "").strip()
    city = (r.get("city") or "").strip()
    zc = (r.get("zip_code") or "").strip()
    if addr and city:
        geo_rows.append((str(idx), addr, city, zc))
print(f"Geocoding {len(geo_rows)} addresses (batch)…")
coords_by_idx = geocode_batch(geo_rows)
print(f"  {len(coords_by_idx)} matched")

out, skipped = [], 0
for idx, r in enumerate(prospects):
    addr = (r.get("actual_address_of_premises") or "").strip()
    city = (r.get("city") or "").strip()
    coords = coords_by_idx.get(str(idx))
    if not coords:
        skipped += 1
        continue

    raw_name = (r.get("dba") or r.get("legalname") or addr).strip()
    appid = r.get("application_id", "")
    received = (r.get("received_date") or "")[:10]
    status = r.get("status", "")

    out.append({
        "id": "sla-" + appid,
        "name": nice_name(raw_name) if not r.get("dba") else raw_name,
        "category": "Restaurant",
        "cuisine": "",
        "street": f"{addr}, {city}",
        "lat": round(coords[0], 6),
        "lng": round(coords[1], 6),
        "fitScore": int(45 + det(appid, "fit") * 55),        # estimate placeholder
        "monthlyValue": int(det(appid, "val") * 2800),        # estimate placeholder
        "status": "new",
        "opening": {
            "type": "soon",
            "stage": status,
            "received": received,
            "source": "NY SLA pending license",
        },
    })

print(f"  built {len(out)} 'opening soon' prospects")

# ---- JUST OPENED: recently issued active licenses (coords already included) ----
cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%dT00:00:00")
descs = "','".join(sorted(KEEP))
where = (f"premisescounty='{COUNTY}' AND originalissuedate > '{cutoff}' "
         f"AND description in('{descs}')")
active_url = (SLA_ACTIVE_RES + "?$limit=500&$where="
              + urllib.parse.quote(where))
print(f"Fetching active licenses issued since {cutoff[:10]}…")
active = fetch(active_url)

# Dedupe against 'opening soon' by rounded coordinate.
seen = {(round(p["lat"], 4), round(p["lng"], 4)) for p in out}
just_opened = 0
for r in active:
    geo = (r.get("georeference") or {}).get("coordinates")
    if not geo:
        continue
    lng, lat = float(geo[0]), float(geo[1])
    key = (round(lat, 4), round(lng, 4))
    if key in seen:
        continue
    seen.add(key)
    lic = r.get("licensepermitid", "")
    issued = (r.get("originalissuedate") or "")[:10]
    addr = (r.get("actualaddressofpremises") or "").strip().title()
    city = (r.get("city") or "").strip().title()
    out.append({
        "id": "sla-active-" + lic,
        "name": nice_name(r.get("legalname")),
        "category": "Restaurant",
        "cuisine": "",
        "street": f"{addr}, {city}",
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "fitScore": int(45 + det(lic, "fit") * 55),
        "monthlyValue": int(det(lic, "val") * 2800),
        "status": "new",
        "opening": {
            "type": "open",
            "stage": "Recently opened",
            "issued": issued,
            "source": "NY SLA new license",
        },
    })
    just_opened += 1
print(f"  added {just_opened} 'just opened' (deduped against pending)")

# Final order: opening-soon first (closest-to-open by SLA stage),
# then just-opened (most recently licensed first).
soon = [p for p in out if p["opening"]["type"] == "soon"]
opened = [p for p in out if p["opening"]["type"] == "open"]
soon.sort(key=lambda p: STAGE_RANK.get(p["opening"]["stage"], 0), reverse=True)
opened.sort(key=lambda p: p["opening"].get("issued", ""), reverse=True)
out = soon + opened

with open("openings.js", "w") as f:
    f.write("// Auto-generated by openings_feed.py — REAL openings from NY SLA pending licenses.\n")
    f.write("// Refresh: python3 openings_feed.py\n")
    f.write(f"// Generated {time.strftime('%Y-%m-%d')} · {len(out)} openings\n")
    f.write("window.REAL_OPENINGS = ")
    json.dump(out, f, ensure_ascii=False)
    f.write(";\n")

print(f"\nwrote {len(out)} real openings -> openings.js  (skipped {skipped} un-geocodable)")
