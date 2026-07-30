"""Chefs' Warehouse fit scoring — shared by build_data.py and openings_feed.py.

The Chefs' Warehouse sells specialty / center-of-plate ingredients to menu-driven
INDEPENDENT restaurants, fine dining, upscale bars, hotels, caterers, and
bakeries/patisseries. Commodity chains and quick-service buy broadline instead.

score_fit(name, category, cuisine) -> (fitScore 0-100, is_chain bool)
"""

# National / regional chains & quick-service that are NOT prospects. Matched as
# lowercase substrings of the venue name. Kept deliberately to true commodity
# chains — local 2-3 unit independents are intentionally NOT here.
CHAINS = {
    "starbucks", "dunkin", "mcdonald", "burger king", "wendy", "subway",
    "chipotle", "shake shack", "five guys", "panera", "chick-fil-a", "kfc",
    "popeyes", "taco bell", "domino", "pizza hut", "papa john", "little caesar",
    "sbarro", "wingstop", "buffalo wild wings", "ihop", "applebee",
    "cheesecake factory", "le pain quotidien", "olive garden", "red lobster",
    "tgi friday", "chili's", "denny", "waffle house", "dairy queen", "sonic",
    "arby", "jersey mike", "jimmy john", "firehouse subs", "potbelly", "qdoba",
    "moe's southwest", "sweetgreen", "cava", "blaze pizza", "& pizza",
    "auntie anne", "cinnabon", "baskin", "cold stone", "crumbl", "insomnia cookies",
    "cobs bread", "pret a manger", "tim horton", "peet's", "dutch bros",
    "7-eleven", "panda express", "checkers", "white castle", "boston market",
    "smashburger", "wingstop", "playa bowls", "juice press", "european wax",
}

def _tok(cuisine):
    c = (cuisine or "").lower().replace(";", ",")
    return [t.strip().replace(" ", "_") for t in c.split(",") if t.strip()]

# Cuisine tiers (tokens use underscores; matched loosely). Chefs' Warehouse targets
# WIDE (WORK-PORTFOLIO.md §6): fast-casual is the biggest growth segment and the net
# includes casual spots, not just white-tablecloth. So casual food-prep operations
# score as real prospects; only beverage/sweet counters sit low.

# Chef-driven / specialty ceiling (fine dining, plus pastry — an underserved CW sweet spot).
HIGH = {"french", "italian", "japanese", "sushi", "seafood", "steak",
        "steak_house", "steakhouse", "mediterranean", "greek", "spanish",
        "contemporary", "american", "ramen", "izakaya", "tapas", "oyster",
        "modern_european", "fine_dining", "basque", "raw", "fusion", "asian",
        "peruvian", "argentinian", "brazilian", "portuguese", "pastry",
        "patisserie", "chocolate", "dessert"}
# Ethnic full-service — solid, buys proteins/oils/specialty.
MED = {"thai", "indian", "chinese", "mexican", "korean", "latin_american",
       "turkish", "vietnamese", "caribbean", "moroccan", "lebanese",
       "ethiopian", "cuban", "middle_eastern", "filipino", "malaysian"}
# Fast-casual / casual food prep — the growth segment. Still buys real product
# (a pizzeria = tomatoes/flour/cheese/oil; a taqueria = proteins/oil). Kept positive.
CASUAL = {"pizza", "burger", "tacos", "taco", "sandwich", "deli", "diner",
          "bbq", "barbecue", "wings", "fried_chicken", "wrap", "cheesesteak",
          "sub", "comfort_food", "hot_dog", "breakfast", "brunch", "salad"}
# Beverage / sweet counters — a specialty food distributor sells little here.
LOW = {"coffee_shop", "coffee", "bagel", "donut", "doughnut", "juice",
       "smoothie", "ice_cream", "bubble_tea", "frozen_yogurt", "tea", "boba"}

# Name signals.
NAME_UP = ("bistro", "trattoria", "osteria", "brasserie", "ristorante", "tavern",
           "chophouse", "steakhouse", "steak house", "oyster", "wine bar",
           "gastropub", "kitchen", "table", "cellar", "brewpub", "supper",
           "patisserie", "chocolat")
NAME_DOWN = ("bagel", "donut", "doughnut", "juice bar", "smoothie", "creamery",
             "ice cream", "frozen yogurt", "coffee roast")

BASE = {"Restaurant": 60, "Bar": 55, "Bakery": 60, "Cafe": 44}

def is_chain(name):
    n = (name or "").lower()
    return any(c in n for c in CHAINS)

def score_fit(name, category, cuisine):
    if is_chain(name):
        return 0, True
    score = BASE.get(category, 55)
    toks = _tok(cuisine)
    if any(t in HIGH for t in toks):
        score += 22
    elif any(t in MED for t in toks):
        score += 12
    elif any(t in CASUAL for t in toks):
        score += 4
    if any(t in LOW for t in toks):
        score -= 16
    n = (name or "").lower()
    if any(w in n for w in NAME_UP):
        score += 10
    if any(w in n for w in NAME_DOWN):
        score -= 10
    return max(30, min(98, score)), False
