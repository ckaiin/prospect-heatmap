#!/usr/bin/env python3
"""Build briefings.js from the researched source files in .briefsrc/.

Adds `cwSellers` to each briefing = the Chefs' Warehouse products projected to be
best-sellers INTO that restaurant (derived from its cuisine/style), replacing the
old menu-based "bestSellers". Rebuild: python3 build_briefings.py
"""
import json, glob, os

SRC_DIR = ".briefsrc"
OUT = "briefings.js"

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

# Merge all source files.
briefings = {}
for f in sorted(glob.glob(os.path.join(SRC_DIR, "*.json"))):
    with open(f) as fh:
        briefings.update(json.load(fh))

for bid, b in briefings.items():
    b.pop("bestSellers", None)          # drop old menu best-sellers
    b["cwSellers"] = cw_sellers(b)      # add CW products to sell them

with open(OUT, "w") as f:
    f.write("// Researched opening briefings, keyed by opening id. Built by build_briefings.py.\n")
    f.write("// cwSellers = CW products projected to sell into that venue (from its cuisine).\n")
    f.write("window.OPENING_BRIEFINGS = ")
    json.dump(briefings, f, ensure_ascii=False)
    f.write(";\n")

print(f"wrote {len(briefings)} briefings -> {OUT}")
