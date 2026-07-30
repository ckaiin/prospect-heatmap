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

# Cuisine tiers (tokens use underscores; matched loosely).
HIGH = {"french", "italian", "japanese", "sushi", "seafood", "steak",
        "steak_house", "steakhouse", "mediterranean", "greek", "spanish",
        "contemporary", "american", "ramen", "izakaya", "tapas", "oyster",
        "modern_european", "fine_dining", "basque", "raw", "fusion", "asian",
        "peruvian", "argentinian", "brazilian", "portuguese"}
MED = {"thai", "indian", "chinese", "mexican", "korean", "latin_american",
       "turkish", "vietnamese", "caribbean", "moroccan", "lebanese",
       "ethiopian", "cuban", "middle_eastern", "filipino", "malaysian"}
LOW = {"pizza", "burger", "tacos", "taco", "wings", "bagel", "sandwich",
       "donut", "doughnut", "coffee_shop", "coffee", "fast_food",
       "fried_chicken", "hot_dog", "deli", "ice_cream", "bubble_tea", "juice",
       "smoothie", "breakfast", "diner", "wrap", "salad", "frozen_yogurt"}

# Name signals.
NAME_UP = ("bistro", "trattoria", "osteria", "brasserie", "ristorante", "tavern",
           "chophouse", "steakhouse", "steak house", "oyster", "wine bar",
           "gastropub", "kitchen", "table", "cellar", "brewpub", "supper")
NAME_DOWN = ("pizzeria", "pizza", "deli", "diner", "bagel", "donut", "doughnut",
             "wings", "express", "taqueria", "halal", "grill express",
             "food truck", "creamery", "frozen", "smoothie", "juice")

BASE = {"Restaurant": 62, "Bar": 55, "Bakery": 52, "Cafe": 34}

def is_chain(name):
    n = (name or "").lower()
    return any(c in n for c in CHAINS)

def score_fit(name, category, cuisine):
    if is_chain(name):
        return 0, True
    score = BASE.get(category, 55)
    toks = _tok(cuisine)
    if any(t in HIGH for t in toks):
        score += 25
    elif any(t in MED for t in toks):
        score += 10
    if any(t in LOW for t in toks):
        score -= 22
    n = (name or "").lower()
    if any(w in n for w in NAME_UP):
        score += 12
    if any(w in n for w in NAME_DOWN):
        score -= 12
    return max(5, min(98, score)), False
