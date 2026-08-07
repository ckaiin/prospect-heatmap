#!/usr/bin/env python3
"""Build briefings.js from the researched source files in .briefsrc/.

Adds `cwSellers` to each briefing = the Chefs' Warehouse products projected to be
best-sellers INTO that restaurant (derived from its cuisine/style), replacing the
old menu-based "bestSellers". Rebuild: python3 build_briefings.py
"""
import json, glob, os, re

SRC_DIR = ".briefsrc"
OUT = "briefings.js"
VENUES = os.path.join(SRC_DIR, "_venues.json")   # persistent id -> {name, street}

# CW product baskets by cuisine bucket (ordered by pitch priority).
PROD = {
    "italian": ["Caputo 00 flour", "Teo San Marzano tomatoes", "fresh mozzarella & burrata",
                "imported Parmigiano/Pecorino", "Grand Reserve butter", "Spiletto olive oil"],
    "steak_american": ["Allen Brothers premium beef", "Grand Reserve butter",
                        "specialty/artisan cheeses", "specialty seafood (surf & turf)"],
    "mexican_latin": ["skirt & flank steak / carnitas", "specialty seafood (shrimp, fish)",
                      "queso fresco / cotija", "Teo tomatoes (salsas)"],
    "peruvian_seafood": ["specialty seafood (fish, shrimp, octopus)",
                         "Allen Brothers beef (lomo/anticuchos)", "whole chickens (rotisserie)"],
    "sushi_japanese": ["sushi-grade seafood (tuna, salmon, yellowtail, uni)",
                       "specialty shellfish", "Allen Brothers beef (hibachi/wagyu)"],
    "asian": ["specialty seafood (shrimp, whole fish)", "premium proteins (pork, chicken, duck)",
              "Grand Reserve butter", "Caputo flour (dumpling/bao)"],
    "med": ["Spiletto olive oil", "imported feta / Manchego / cheeses",
            "specialty seafood (octopus, branzino)", "Allen Brothers lamb & beef"],
    "bakery": ["Grand Reserve butter", "Caputo / pastry flour",
               "Valrhona & Chicoa chocolate", "specialty cheeses"],
    "caribbean": ["proteins: oxtail, goat, jerk chicken", "specialty seafood (snapper)",
                  "Grand Reserve butter"],
    "bbq_deli": ["Allen Brothers brisket & short rib", "imported cheeses",
                 "Grand Reserve butter", "Spiletto olive oil"],
    "diner": ["Grand Reserve butter", "Allen Brothers beef (burgers/steak)", "specialty cheeses"],
}

KW = {
    "italian": ["italian", "pizza", "pizzeria", "trattoria", "ristorante", "pasta", "neapolitan",
                "sicilian", "calabrese", " roman", "parm", "marinara", "salumeria", "gnocchi",
                "risotto", "mozzarella", "calzone"],
    "steak_american": ["steakhouse", "steak house", "chophouse", "steak", "gastropub", "tavern",
                       "bar & grill", "bar and grill", "sports bar", "brasserie", "new american",
                       " pub", "burger", "wings"],
    "mexican_latin": ["mexican", "taco", "taqueria", "birria", "carne asada", "enchilada",
                      "guacamole", "margarita", " latin", "salvadoran", "guatemalan", "colombian",
                      "cuban", "pupusa", "ropa vieja", "mariscos"],
    "peruvian_seafood": ["peruvian", "ceviche", "lomo saltado", "pollo a la brasa", "anticuchos",
                         "aguachile"],
    "sushi_japanese": ["sushi", "sashimi", "omakase", "nigiri", "japanese", "hibachi", "ramen",
                       "izakaya", "teppanyaki"],
    "asian": ["thai", "chinese", "szechuan", "sichuan", "dim sum", "dumpling", "vietnamese", "pho",
              " wok", "cantonese", "malaysian", "himalayan", "momo", "curry", "korean", "asian",
              "noodle", "wonton", " bao", "peking"],
    "med": ["greek", "mediterranean", "taverna", "turkish", "meze", "kebab", "souvlaki", "spanish",
            "tapas", "andaluz", "paella", "feta", "branzino", "gyro"],
    "bakery": ["bakery", "pastry", "patisserie", "tearoom", "tea room", "scone", "cafe", "coffee",
               "dessert", "gelato", "chocolate", "pie company", "baked", "brunch bakery"],
    "caribbean": ["jamaican", "caribbean", " jerk", "oxtail", "curry goat", "dominican"],
    "bbq_deli": ["bbq", "barbecue", "smoked", "brisket", "sandwich", " deli", "charcuterie",
                 "salumi", " hero", " sub "],
    "diner": ["diner", "breakfast", "comfort food", "all-day", "24/7"],
}

GENERIC = ["Allen Brothers premium beef", "specialty seafood", "Grand Reserve butter",
           "imported cheeses", "Spiletto olive oil"]

def cw_sellers(b):
    text = " ".join([b.get("style", ""), b.get("menu", ""), b.get("summary", ""),
                     b.get("angle", "")]).lower()
    scores = {}
    for bucket, kws in KW.items():
        s = sum(text.count(k) for k in kws)
        if s:
            scores[bucket] = s
    if not scores:
        return list(GENERIC)
    top = sorted(scores, key=lambda k: -scores[k])[:2]
    out = []
    for bucket in top:
        for p in PROD[bucket]:
            if p not in out:
                out.append(p)
    return out[:6]

# Merge all source files (skip the _venues registry, which isn't a briefing file).
briefings = {}
for f in sorted(glob.glob(os.path.join(SRC_DIR, "*.json"))):
    if os.path.basename(f).startswith("_"):
        continue
    with open(f) as fh:
        briefings.update(json.load(fh))

for bid, b in briefings.items():
    b.pop("bestSellers", None)          # drop old menu best-sellers
    b["cwSellers"] = cw_sellers(b)      # add CW products to sell them


# ---- Alias map -------------------------------------------------------------
# A venue's SLA id CHANGES when it graduates from a pending license to an active
# one (sla-NA-... -> sla-active-...), which would orphan its researched briefing.
# So we also key briefings by normalized address, and let the page fall back to
# that when the id misses. `_venues.json` is a persistent id -> name/street
# registry, refreshed from openings.js on every build so ids that have already
# rolled off the feed keep resolving.

def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(street|st|avenue|ave|road|rd|drive|dr|lane|ln|place|pl|"
               r"boulevard|blvd|suite|ste|unit|north|south|east|west|n|s|e|w)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

venues = {}
if os.path.exists(VENUES):
    with open(VENUES) as fh:
        venues = json.load(fh)

# Refresh the registry from the current openings feed (union — never drop ids).
if os.path.exists("openings.js"):
    txt = open("openings.js").read()
    for o in json.loads(txt[txt.index("["):txt.rindex("]") + 1]):
        venues[o["id"]] = {"name": o["name"], "street": o["street"]}
    with open(VENUES, "w") as fh:
        json.dump(venues, fh, ensure_ascii=False, indent=0, sort_keys=True)

# street -> briefed ids at that street, to keep street-only matches unambiguous.
by_street = {}
for bid in briefings:
    v = venues.get(bid)
    if v:
        by_street.setdefault(norm(v["street"]), []).append(bid)

aliases = {}
for bid in briefings:
    v = venues.get(bid)
    if not v:
        continue
    aliases[norm(v["name"]) + "|" + norm(v["street"])] = {"id": bid, "exact": True}
for street, ids in by_street.items():
    if len(ids) == 1:                    # only alias an address that's unambiguous
        aliases.setdefault(street, {"id": ids[0], "exact": False})

with open(OUT, "w") as f:
    f.write("// Researched opening briefings, keyed by opening id. Built by build_briefings.py.\n")
    f.write("// cwSellers = CW products projected to sell into that venue (from its cuisine).\n")
    f.write("window.OPENING_BRIEFINGS = ")
    json.dump(briefings, f, ensure_ascii=False)
    f.write(";\n")
    f.write("// Fallback lookup: normalized 'name|street' (and unambiguous street alone)\n")
    f.write("// -> briefing id, so a briefing survives the SLA pending->active id change.\n")
    f.write("window.BRIEFING_ALIASES = ")
    json.dump(aliases, f, ensure_ascii=False)
    f.write(";\n")

print(f"wrote {len(briefings)} briefings, {len(aliases)} aliases -> {OUT}")
