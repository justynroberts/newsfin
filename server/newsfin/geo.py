"""Where a story is actually about.

The feed a headline arrived on is a poor guide to its geography. The Guardian's
UK edition runs Afghanistan coverage; the BBC's top-stories feed carries the
world. Filing by feed puts foreign reporting on the UK tab, which is exactly
the thing a region-tabbed reader notices first.

So the region is inferred from the headline itself and only falls back to the
feed when the text says nothing geographic. This is a lexicon, not a model:
it has to run over thousands of headlines per poll, and a place name is one of
the few things in a headline that is genuinely unambiguous.
"""

from __future__ import annotations

import re

# Each marker is matched as a whole word (or phrase) against the lowercased
# headline. Weights: 2 for something that can only mean this region, 1 for a
# strong-but-shareable hint.
MARKERS: dict[str, dict[str, int]] = {
    "uk": {
        "uk": 2, "u.k.": 2, "britain": 2, "british": 2, "briton": 2, "britons": 2,
        "england": 2, "english": 1, "wales": 2, "welsh": 2, "scotland": 2,
        "scottish": 2, "northern ireland": 2,
        "westminster": 2, "downing street": 2, "whitehall": 2, "holyrood": 2,
        "no 10": 2, "number 10": 2, "commons": 2, "house of lords": 2,
        "starmer": 2, "badenoch": 2, "farage": 2, "reform uk": 2, "davey": 1,
        "labour": 1, "tory": 2, "tories": 2, "conservatives": 1, "lib dem": 2,
        "snp": 2, "sinn fein": 1, "plaid cymru": 2,
        "nhs": 2, "hmrc": 2, "dwp": 2, "ofgem": 2, "ofcom": 2, "ofsted": 2,
        "dvla": 2, "met office": 2, "met police": 2, "network rail": 2,
        "bank of england": 2, "ftse": 2, "sterling": 1, "hs2": 2,
        "universal credit": 2, "national insurance": 2, "council tax": 2,
        "a-level": 2, "gcse": 2, "premier league": 1, "wimbledon": 2,
        "king charles": 2, "buckingham palace": 2, "royal family": 1,
        "london": 2, "manchester": 2, "birmingham": 2, "liverpool": 2,
        "leeds": 2, "sheffield": 2, "glasgow": 2, "edinburgh": 2, "cardiff": 2,
        "belfast": 2, "bristol": 2, "newcastle": 2, "nottingham": 2,
        "southampton": 2, "brighton": 2, "oxford": 1, "cambridge": 1,
        "yorkshire": 2, "cornwall": 2, "devon": 2, "kent": 2, "essex": 2,
        "surrey": 2, "sussex": 2, "norfolk": 2, "suffolk": 2, "heathrow": 2,
        "gatwick": 2,
    },
    "ie": {
        "ireland": 2, "irish": 2, "dublin": 2, "cork": 2, "galway": 2,
        "taoiseach": 2, "dail": 2, "dáil": 2, "garda": 2, "gardai": 2,
        "gardaí": 2, "oireachtas": 2, "tanaiste": 2, "leinster house": 2,
        "fianna fail": 2, "fine gael": 2, "rte": 2,
    },
    "us": {
        "us": 1, "u.s.": 2, "america": 2, "american": 2, "americans": 2,
        "united states": 2, "washington": 2, "white house": 2, "congress": 2,
        "senate": 1, "capitol hill": 2, "pentagon": 2, "supreme court": 1,
        "trump": 2, "biden": 2, "harris": 1, "vance": 1, "maga": 2,
        "republican": 2, "republicans": 2, "democrat": 2, "democrats": 2,
        "gop": 2, "fbi": 2, "cia": 1, "ice": 1, "doj": 2, "fda": 2, "cdc": 2,
        "federal reserve": 2, "wall street": 2, "nasdaq": 2, "dow jones": 2,
        "new york": 2, "california": 2, "texas": 2, "florida": 2, "chicago": 2,
        "los angeles": 2, "boston": 2, "michigan": 2, "ohio": 2, "georgia": 1,
        "pennsylvania": 2, "arizona": 2, "nevada": 2, "seattle": 2,
        "nfl": 2, "nba": 2, "super bowl": 2, "hollywood": 2,
    },
    "eu": {
        "eu": 2, "european union": 2, "brussels": 2, "european commission": 2,
        "european parliament": 2, "eurozone": 2, "schengen": 2, "nato": 1,
        "france": 2, "french": 2, "paris": 2, "macron": 2,
        "germany": 2, "german": 2, "berlin": 2, "merz": 2, "bundestag": 2,
        "spain": 2, "spanish": 2, "madrid": 2, "barcelona": 2,
        "italy": 2, "italian": 2, "rome": 2, "meloni": 2,
        "netherlands": 2, "dutch": 2, "amsterdam": 2,
        "belgium": 2, "poland": 2, "polish": 2, "warsaw": 2,
        "portugal": 2, "greece": 2, "greek": 2, "athens": 2,
        "sweden": 2, "norway": 2, "denmark": 2, "finland": 2, "austria": 2,
        "switzerland": 2, "swiss": 2, "hungary": 2, "orban": 2, "romania": 2,
        "czech": 2, "slovakia": 2, "croatia": 2, "serbia": 2, "bulgaria": 2,
        "ukraine": 2, "ukrainian": 2, "kyiv": 2, "zelensky": 2, "zelenskyy": 2,
        "russia": 1, "russian": 1, "moscow": 2, "putin": 2, "kremlin": 2,
        "ecb": 2, "euro": 1,
    },
    # Without an explicit world list, anything the other lexicons miss falls
    # back to its feed - which is how Afghanistan coverage ends up on the UK
    # tab. These are the places that generate international news.
    "world": {
        "china": 2, "chinese": 2, "beijing": 2, "shanghai": 2, "xi jinping": 2,
        "hong kong": 2, "taiwan": 2, "taipei": 2,
        "india": 2, "indian": 1, "delhi": 2, "mumbai": 2, "modi": 2,
        "pakistan": 2, "islamabad": 2, "bangladesh": 2, "sri lanka": 2,
        "japan": 2, "japanese": 2, "tokyo": 2,
        "korea": 2, "korean": 2, "seoul": 2, "pyongyang": 2, "kim jong un": 2,
        "afghanistan": 2, "afghan": 2, "kabul": 2, "taliban": 2,
        "iran": 2, "iranian": 2, "tehran": 2, "iraq": 2, "baghdad": 2,
        "syria": 2, "syrian": 2, "damascus": 2, "lebanon": 2, "beirut": 2,
        "hezbollah": 2, "yemen": 2, "houthi": 2,
        "israel": 2, "israeli": 2, "gaza": 2, "west bank": 2, "netanyahu": 2,
        "hamas": 2, "palestinian": 2, "palestinians": 2, "jerusalem": 2,
        "saudi": 2, "saudi arabia": 2, "riyadh": 2, "uae": 2, "dubai": 2,
        "qatar": 2, "doha": 2, "turkey": 2, "erdogan": 2, "istanbul": 2,
        "egypt": 2, "cairo": 2, "libya": 2, "sudan": 2, "ethiopia": 2,
        "somalia": 2, "kenya": 2, "nairobi": 2, "nigeria": 2, "lagos": 2,
        "ghana": 2, "congo": 2, "rwanda": 2, "zimbabwe": 2,
        "south africa": 2, "johannesburg": 2, "cape town": 2,
        "brazil": 2, "brazilian": 2, "sao paulo": 2, "rio de janeiro": 2,
        "argentina": 2, "buenos aires": 2, "chile": 2, "colombia": 2,
        "venezuela": 2, "peru": 2, "bolivia": 2, "cuba": 2, "haiti": 2,
        "mexico": 2, "mexican": 2, "canada": 2, "canadian": 2, "ottawa": 2,
        "toronto": 2, "australia": 2, "australian": 2, "sydney": 2,
        "melbourne": 2, "new zealand": 2, "indonesia": 2, "jakarta": 2,
        "philippines": 2, "manila": 2, "vietnam": 2, "thailand": 2,
        "bangkok": 2, "myanmar": 2, "singapore": 2, "malaysia": 2,
        "united nations": 2, "who": 1, "imf": 2, "world bank": 2,
        "opec": 2, "cop30": 2, "cop31": 2,
    },
}

# Sub-UK areas. Only consulted once a headline already reads as UK, so
# "Birmingham, Alabama" does not pull a US story onto the Local tab.
LOCALE_MARKERS: dict[str, tuple[str, ...]] = {
    "london": ("london", "westminster", "croydon", "hackney", "camden", "brixton",
               "wembley", "heathrow", "islington", "southwark", "greenwich"),
    "manchester": ("manchester", "salford", "stockport", "oldham", "rochdale", "bolton", "wigan"),
    "liverpool": ("liverpool", "merseyside", "wirral", "birkenhead", "sefton"),
    "birmingham": ("birmingham", "west midlands", "wolverhampton", "coventry",
                   "dudley", "walsall", "solihull"),
    "leeds": ("leeds", "west yorkshire", "bradford", "wakefield", "huddersfield", "halifax"),
    "sheffield": ("sheffield", "south yorkshire", "rotherham", "doncaster", "barnsley"),
    "newcastle": ("newcastle", "gateshead", "sunderland", "tyneside", "durham", "northumberland"),
    "bristol": ("bristol", "somerset", "bath", "gloucester", "swindon"),
    "nottingham": ("nottingham", "nottinghamshire", "mansfield", "derby"),
    "kent": ("kent", "canterbury", "maidstone", "dover", "medway", "margate"),
    "sussex": ("sussex", "brighton", "hove", "eastbourne", "hastings", "crawley"),
    "hampshire": ("hampshire", "southampton", "portsmouth", "winchester", "basingstoke"),
    "devon": ("devon", "exeter", "plymouth", "torquay"),
    "cornwall": ("cornwall", "truro", "penzance", "newquay", "falmouth"),
    "eastanglia": ("norfolk", "suffolk", "norwich", "ipswich", "cambridge",
                   "peterborough", "colchester", "great yarmouth"),
    "scotland": ("scotland", "scottish", "glasgow", "edinburgh", "aberdeen",
                 "dundee", "inverness", "holyrood", "snp"),
    "wales": ("wales", "welsh", "cardiff", "swansea", "newport", "wrexham", "senedd"),
    "ni": ("northern ireland", "belfast", "derry", "londonderry", "stormont", "ulster"),
}


def _compile(markers: dict[str, int]) -> list[tuple[re.Pattern, int]]:
    out = []
    for phrase, weight in markers.items():
        escaped = re.escape(phrase)
        out.append((re.compile(rf"(?<![\w']){escaped}(?![\w'])", re.IGNORECASE), weight))
    return out


_COMPILED = {region: _compile(m) for region, m in MARKERS.items()}
_LOCALE_COMPILED = {
    locale: [re.compile(rf"(?<![\w']){re.escape(p)}(?![\w'])", re.IGNORECASE) for p in phrases]
    for locale, phrases in LOCALE_MARKERS.items()
}


def score_regions(text: str) -> dict[str, int]:
    return {
        region: sum(w for pattern, w in patterns if pattern.search(text))
        for region, patterns in _COMPILED.items()
    }


def classify(text: str, fallback: str = "world") -> tuple[str, int]:
    """Best region for this headline and the confidence behind it.

    Confidence is the winning weight minus the runner-up, so a headline naming
    both Britain and Brussels scores low and keeps its feed-derived region
    rather than being forced onto one tab.
    """
    scores = score_regions(text)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top, top_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    if top_score == 0:
        return fallback, 0
    return top, top_score - runner_up


def detect_locale(text: str) -> str | None:
    """Sub-UK area, or None. Only meaningful for text already judged UK."""
    best, best_hits = None, 0
    for locale, patterns in _LOCALE_COMPILED.items():
        hits = sum(1 for p in patterns if p.search(text))
        if hits > best_hits:
            best, best_hits = locale, hits
    return best


def resolve_region(text: str, feed_region: str) -> str:
    """Final region for a story.

    The headline wins when it is unambiguous. Otherwise the feed's own region
    stands - a Manchester Evening News story with no place name in the headline
    is still local news.
    """
    region, confidence = classify(text, fallback=feed_region)

    # A confident non-UK reading overrides a UK-edition feed. This is the case
    # that matters: national outlets publish the world on their home feeds.
    if confidence >= 2 and region != feed_region:
        # UK text arriving on a local feed keeps the local filing - "local" is
        # a sub-region of UK, not a competitor to it.
        if region == "uk" and feed_region == "local":
            return "local"
        return region

    # No geographic signal at all: trust the feed.
    if confidence == 0:
        return feed_region

    return region if region == feed_region else feed_region
