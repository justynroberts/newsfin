"""Headline normalisation and similarity.

Clustering the same story across 200 newsrooms is the whole trick behind
impact ranking, and it has to run on a phone-facing API in milliseconds. So:
no ML, no embeddings - token sets, IDF weighting and a blocking index.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

# Words that carry no signal about *which* story this is. Deliberately small:
# over-stripping merges unrelated stories, which is far worse than under-
# stripping (which merely splits one story into two rows).
STOPWORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for from by with
about into over after before under above between during against through is are was were
be been being am has have had do does did will would shall should can could may might must
it its it's as not no nor so such own same too very just also more most other some any
he she they them his her their we you i us our your who whom which what when where why how
says say said told after amid says new latest live updates says report reports according
first two three four five one out up down off out
""".split())

# Dates are poison for clustering. "August 2026" appears in a NASA picture of
# the day, a Euronews bulletin and forty WIRED promo-code pages, and because
# it is capitalised it also reads as a shared proper noun - so the entity
# assist merged all of them into one cluster. Dates never identify a story.
DATE_WORDS = frozenset("""
january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec
monday tuesday wednesday thursday friday saturday sunday
mon tue tues wed thu thur thurs fri sat sun
today tomorrow yesterday tonight morning afternoon evening weekend week month year
am pm gmt bst utc edt est
""".split())

STOPWORDS = STOPWORDS | DATE_WORDS

_WORD = re.compile(r"[a-z0-9']+")
_ALL_DIGITS = re.compile(r"^[0-9']+$")
_TRAILING_SOURCE = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")

# Different newsrooms describe the same event with different nouns. Without
# this, "7.7 quake hits Indonesia" and "magnitude 7.7 earthquake in Indonesia"
# stay in separate clusters and the biggest story of the day looks like four
# medium ones.
SYNONYMS = {
    "quake": "earthquake", "tremor": "earthquake",
    "blast": "explosion", "bomb": "explosion",
    "slain": "kill", "fatal": "kill", "died": "kill", "death": "kill", "dead": "kill",
    "wounded": "injure", "hurt": "injure",
    "premier": "pm", "primeminister": "pm",
    "cop": "police", "officer": "police",
    "jail": "prison", "imprisoned": "prison",
    "row": "dispute", "spat": "dispute",
    "hike": "rise", "climb": "rise", "soar": "rise", "jump": "rise",
    "slump": "fall", "plunge": "fall", "tumble": "fall", "drop": "fall",
    "poll": "election", "vote": "election", "ballot": "election",
    "quit": "resign", "steps": "resign", "stepdown": "resign",
    "gaza": "gaza", "ukraine": "ukraine",
}


def normalise(title: str) -> str:
    """Lowercase, strip accents/punctuation and the trailing ' - Publisher'."""
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("‘", "'")
    t = _TRAILING_SOURCE.sub("", t)
    return t.lower().strip()


def stem(word: str) -> str:
    """Crude suffix stripper. Good enough to make kills/killed/killing match,
    which is most of what headline clustering needs from a stemmer."""
    for suffix, keep in (("ies", 3), ("ing", 4), ("ed", 3), ("es", 3), ("s", 3)):
        if word.endswith(suffix) and len(word) - len(suffix) >= keep:
            base = word[: -len(suffix)]
            if suffix == "ies":
                base += "y"
            return base
    return word


def tokens(title: str) -> list[str]:
    out = []
    for raw in _WORD.findall(normalise(title)):
        # Quoted headline fragments ("don't drive", terminals 'closed') leave
        # apostrophes welded to the token, so road and road' became two
        # different words and diluted the overlap between two reports of the
        # same event.
        w = raw.strip("'")
        if w in STOPWORDS or len(w) < 3:
            continue
        # Bare numbers ("2026", "300") never identify which story this is.
        if _ALL_DIGITS.match(w):
            continue
        w = SYNONYMS.get(w, w)
        w = stem(w)
        out.append(SYNONYMS.get(w, w))
    return out


def token_set(title: str) -> frozenset[str]:
    return frozenset(tokens(title))


def content_key(title: str) -> str:
    """Stable hash of the significant tokens - catches verbatim syndication."""
    return hashlib.sha1(" ".join(sorted(token_set(title))).encode()).hexdigest()[:16]


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def containment(a: frozenset[str], b: frozenset[str]) -> float:
    """Overlap as a fraction of the *smaller* set.

    Headlines vary wildly in length - 'Bank of England holds rates' vs
    'Bank of England holds interest rates at 4% as inflation cools, governor
    signals cuts ahead'. Jaccard punishes that pairing; containment does not.
    """
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    """Blend of the two, biased towards containment for uneven lengths."""
    return max(jaccard(a, b), 0.85 * containment(a, b))


def trigrams(title: str) -> frozenset[str]:
    """Character 3-grams over the normalised, space-collapsed headline.

    Token overlap is blind to spelling drift - 'Zelensky' vs 'Zelenskyy',
    'Erdogan' vs 'Erdoğan', 'Labour' vs 'Labor'. Character n-grams see through
    all of it, and they cost nothing to compute.
    """
    s = " " + re.sub(r"[^a-z0-9 ]+", "", normalise(title)) + " "
    s = re.sub(r"\s+", " ", s)
    if len(s) < 3:
        return frozenset()
    return frozenset(s[i : i + 3] for i in range(len(s) - 2))


def trigram_similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / min(len(a), len(b))


class IdfModel:
    """Inverse document frequency over the live headline corpus.

    Unweighted overlap treats 'indonesia' and 'least' as equally informative,
    which is why plain Jaccard splits one earthquake into four stories. IDF
    makes the rare, story-identifying words carry the decision.
    """

    __slots__ = ("df", "n", "_cache")

    def __init__(self, documents: list[frozenset[str]] | None = None):
        self.df: dict[str, int] = {}
        self.n = 0
        self._cache: dict[str, float] = {}
        for doc in documents or []:
            self.add(doc)

    def add(self, doc: frozenset[str]) -> None:
        self.n += 1
        for t in doc:
            self.df[t] = self.df.get(t, 0) + 1
        self._cache.clear()

    def weight(self, token: str) -> float:
        w = self._cache.get(token)
        if w is None:
            # +1 smoothing; unseen tokens are treated as maximally rare.
            w = math.log((self.n + 1) / (1 + self.df.get(token, 0))) + 1.0
            self._cache[token] = w
        return w

    def mass(self, doc: frozenset[str]) -> float:
        return sum(self.weight(t) for t in doc)

    def similarity(self, a: frozenset[str], b: frozenset[str]) -> float:
        """Weighted containment: shared informative mass over the smaller side.

        Containment rather than Jaccard because headline lengths vary hugely
        between a wire brief and a broadsheet standfirst.
        """
        if not a or not b:
            return 0.0
        shared = a & b
        if not shared:
            return 0.0
        inter = self.mass(shared)
        return inter / min(self.mass(a), self.mass(b))

    def fuzzy(
        self,
        a_tokens: frozenset[str],
        b_tokens: frozenset[str],
        a_grams: frozenset[str],
        b_grams: frozenset[str],
    ) -> float:
        """Combined same-story confidence, 0..1.

        Two independent views of the headline pair, deliberately combined
        rather than averaged blindly:

          * IDF token overlap - semantic, robust to word order, but blind to
            spelling and to headlines that share meaning through phrasing.
          * Character trigram overlap - catches transliteration and spelling
            drift, but easily fooled by common English boilerplate.

        Either one being very strong is sufficient evidence on its own, so we
        take the max of the blend and each individual signal at its own high
        bar. That is what makes it fuzzy rather than a brittle AND.
        """
        lex = self.similarity(a_tokens, b_tokens)
        chr_ = trigram_similarity(a_grams, b_grams)
        blend = 0.62 * lex + 0.38 * chr_
        # A near-verbatim headline (syndicated wire copy) should merge even if
        # its distinctive tokens happen to be common ones.
        if chr_ >= 0.80:
            return max(blend, chr_)
        # Conversely, overwhelming rare-token agreement stands on its own.
        if lex >= 0.85:
            return max(blend, lex)
        return blend


# Proper-noun-ish tokens (capitalised in the original) are the strongest
# evidence that two headlines are about the same event.
_CAP = re.compile(r"\b([A-Z][a-zA-Z'’]{2,})")


def entities(title: str) -> frozenset[str]:
    # The leading word is kept, even though every headline starts capitalised.
    # Dropping it lost "Heathrow" from "Heathrow Airport pipe leak causes
    # flood disruption" and split one airport closure into three stories.
    #
    # The false positives this admits - "Man", "Police", "New" - are handled
    # far better downstream: they appear in hundreds of headlines, so their IDF
    # weight is low and the rarity test rejects them anyway. A frequency test
    # beats a positional guess.
    words = _CAP.findall(title)
    return frozenset(
        w.lower() for w in words
        if w.lower() not in STOPWORDS and not _ALL_DIGITS.match(w.lower())
    )
