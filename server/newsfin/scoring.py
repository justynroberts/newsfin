"""Impact scoring.

The ordering question this app answers is "what actually matters right now",
not "what is newest". Recency is a component, never the driver - otherwise a
routine press release published 90 seconds ago outranks a war.

The dominant signal is **corroboration**: how many independent newsrooms have
independently decided a story is worth their front page. That is a real-world
editorial vote, aggregated across ~230 outlets, and it is very hard to fake.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

# Words that mark consequence. Weighted, not binary: "dies" is not "wins".
SEVERITY: dict[str, float] = {
    # loss of life / disaster
    "killed": 1.0, "dead": 1.0, "dies": 0.9, "death": 0.85, "deaths": 0.95,
    "massacre": 1.0, "earthquake": 1.0, "tsunami": 1.0, "hurricane": 0.9,
    "wildfire": 0.8, "flood": 0.8, "floods": 0.8, "explosion": 0.9, "crash": 0.85,
    "collapse": 0.8, "outbreak": 0.85, "pandemic": 1.0, "famine": 0.95,
    "evacuated": 0.75, "casualties": 0.95, "injured": 0.7, "missing": 0.6,
    # conflict / security
    "war": 1.0, "invasion": 1.0, "strikes": 0.7, "airstrike": 0.9, "missile": 0.85,
    "ceasefire": 0.9, "hostages": 0.9, "terror": 0.9, "attack": 0.8, "shooting": 0.85,
    "nuclear": 0.9, "troops": 0.7, "sanctions": 0.7, "coup": 1.0, "hack": 0.6,
    "breach": 0.65, "ransomware": 0.6,
    # politics / institutions
    "resigns": 0.9, "resignation": 0.85, "impeachment": 0.95, "election": 0.8,
    "referendum": 0.85, "verdict": 0.75, "convicted": 0.75, "arrested": 0.7,
    "sentenced": 0.7, "inquiry": 0.6, "scandal": 0.7, "ruling": 0.6,
    "sacked": 0.7, "ousted": 0.8, "emergency": 0.85, "summit": 0.6,
    "budget": 0.7, "strike": 0.65, "walkout": 0.6, "treaty": 0.7,
    # economy - direct household impact
    "inflation": 0.8, "recession": 0.9, "interest": 0.6, "rates": 0.6,
    "unemployment": 0.75, "layoffs": 0.7, "bailout": 0.8, "default": 0.85,
    "tariffs": 0.75, "crisis": 0.85, "shortage": 0.7, "bankrupt": 0.75,
    "collapsed": 0.8, "plunge": 0.65, "surge": 0.5,
    # markers of editorial urgency
    "breaking": 0.7, "urgent": 0.7, "warning": 0.6, "alert": 0.6,
}

# Noise the score should actively push down the page.
DEPRESSORS = {
    "recipe": 0.5, "horoscope": 0.7, "quiz": 0.5, "deal": 0.35, "deals": 0.35,
    "discount": 0.4, "shoppers": 0.4, "review": 0.25, "best": 0.2,
    "gift": 0.4, "sale": 0.35, "trailer": 0.3, "recap": 0.3, "spoilers": 0.5,
    "celebrity": 0.3, "kardashian": 0.6, "royal": 0.15, "wordle": 0.8,
    "sponsored": 0.9, "advertorial": 0.9, "opinion": 0.2, "explained": 0.1,
}

_WORD = re.compile(r"[a-z']+")

# Outright non-news that some feeds mix into their news channel: affiliate
# commerce, coupon pages, daily puzzle answers. Dropped at ingest rather than
# merely ranked down - it should never occupy a row in a morning briefing.
_JUNK = re.compile(
    r"\b(promo\s*code|coupon|discount\s*code|voucher\s*code|deal\s*of\s*the\s*day"
    r"|% off|percent off|save up to|best deals|prime day"
    r"|wordle .{0,12}(answer|hint)|connections .{0,12}(answer|hint)"
    r"|quordle|strands .{0,12}(answer|hint)|crossword clue"
    r"|horoscope|your stars|tarot"
    r"|week in (images|pictures)|apod|picture of the (day|week)"
    r"|latest news bulletin|news bulletin)\b",
    re.IGNORECASE,
)

# Headline prefixes that mark a promo or a format rather than the story
# itself. A cluster led by "Watch: what happens if..." reads badly when the
# same cluster contains eleven outlets stating what actually happened.
_WEAK_LEAD = re.compile(
    r"^\s*(watch|video|live|listen|podcast|in pictures|in charts|in maps|gallery"
    r"|analysis|opinion|comment|editorial|explainer|explained|recap|as it happened"
    r"|blog|liveblog|updates|photos|photo essay|briefing|newsletter)\b[\s:|—–-]",
    re.IGNORECASE,
)


# A live blog keeps its published time moving as it is updated, so with recency
# worth a third of the score it floats indefinitely - two football live blogs
# had taken residence in the top ten. The marker is usually a trailing "- live"
# rather than a leading one, which the weak-lead pattern below never caught.
_LIVE_BLOG = re.compile(
    r"(\s[-|–—:]\s*live\s*$|\blive\s+(updates|blog|coverage|reaction)\b"
    r"|\bas it happened\b|\bliveblog\b|\brolling coverage\b)",
    re.IGNORECASE,
)


def is_live_blog(title: str) -> bool:
    """A continuously updated page rather than a new story."""
    return bool(_LIVE_BLOG.search(title))


def is_junk(title: str) -> bool:
    """True for commerce/puzzle/format filler that should never be ingested."""
    return bool(_JUNK.search(title))


def lead_penalty(title: str) -> float:
    """How unsuitable this headline is as the cluster's public face, 0..1."""
    penalty = 0.0
    if _WEAK_LEAD.match(title):
        penalty += 0.6
    if title.endswith("?"):
        # A question headline rarely states the news; prefer one that does.
        penalty += 0.2
    if len(title) < 30:
        penalty += 0.15
    return min(1.0, penalty)


def _now() -> datetime:
    return datetime.now(UTC)


def severity_score(title: str) -> float:
    """0..1 lexical consequence score, saturating so keyword stuffing can't win."""
    words = set(_WORD.findall(title.lower()))
    hits = [SEVERITY[w] for w in words if w in SEVERITY]
    if not hits:
        return 0.0
    hits.sort(reverse=True)
    # Diminishing returns: first term full weight, second half, third quarter.
    total = sum(h * (0.5**i) for i, h in enumerate(hits[:4]))
    return min(1.0, total / 1.6)


def noise_penalty(title: str) -> float:
    """0..1 - how much this looks like commerce/filler rather than news."""
    words = set(_WORD.findall(title.lower()))
    hits = [DEPRESSORS[w] for w in words if w in DEPRESSORS]
    return min(1.0, sum(hits)) if hits else 0.0


#: Hours for a story's recency component to halve.
#:
#: Was 7h, which combined with a lower recency weight left the median age of
#: the top fifteen at over nine hours - the front page was reliably yesterday.
#: At 5h the list turns over through the day while an overnight story is still
#: findable at breakfast.
RECENCY_HALF_LIFE_HOURS = 5.0


def recency_score(published: datetime, half_life_hours: float = RECENCY_HALF_LIFE_HOURS) -> float:
    """Exponential decay, so newer is always better, all else being equal."""
    age_h = max(0.0, (_now() - published).total_seconds() / 3600.0)
    return 0.5 ** (age_h / half_life_hours)


def corroboration_score(distinct_sources: int, aggregator_sources: int = 0) -> float:
    """Log-scaled so 1->2 sources matters far more than 14->15.

    Aggregator feeds (Google News) are counted at a third of a newsroom -
    they republish rather than independently report.
    """
    effective = max(0.0, distinct_sources - aggregator_sources) + aggregator_sources * 0.34
    if effective <= 0:
        return 0.0
    return min(1.0, math.log1p(effective) / math.log1p(12))


def velocity_score(sources_last_hour: int) -> float:
    """How fast outlets are piling on. Distinguishes a breaking event from a
    slow-burn story that happens to have accumulated coverage over two days."""
    if sources_last_hour <= 0:
        return 0.0
    return min(1.0, math.log1p(sources_last_hour) / math.log1p(6))


def prominence_score(best_position: int) -> float:
    """Position in the source feed. Item 0 is that newsroom's lead story."""
    return 1.0 / (1.0 + best_position / 6.0)


# Corroboration and recency now carry equal weight.
#
# Measured against a live snapshot of 200 scored stories: at 0.38/0.18 the
# median age of the top fifteen was 9.2 hours and only a third of it was less
# than six hours old. Moving to 0.30/0.30 with a 5h half-life brings that to
# 2.9 hours with eleven of fifteen under six - and a 30-source earthquake still
# holds third place, which is the test that matters.
#
# Pushing recency further (0.38, 4h half-life) was tried and rejected: it put a
# UFC result and a cricket score above the earthquake. At that point the app is
# a wire feed, not an impact ranking.
WEIGHTS = {
    "corroboration": 0.30,
    "authority": 0.14,
    "recency": 0.30,
    "severity": 0.12,
    "prominence": 0.07,
    "velocity": 0.07,
}


def impact(
    *,
    distinct_sources: int,
    aggregator_sources: int,
    max_authority: float,
    mean_authority: float,
    published: datetime,
    title: str,
    best_position: int,
    sources_last_hour: int,
) -> tuple[float, dict[str, float]]:
    """Return (0..100 impact, per-component breakdown for the API/debug view)."""
    parts = {
        "corroboration": corroboration_score(distinct_sources, aggregator_sources),
        # Blend best-and-average so one prestige outlet lifts a story, but a
        # wall of low-trust tabloids does not.
        "authority": 0.6 * max_authority + 0.4 * mean_authority,
        "recency": recency_score(published),
        "severity": severity_score(title),
        "prominence": prominence_score(best_position),
        "velocity": velocity_score(sources_last_hour),
    }
    base = sum(WEIGHTS[k] * v for k, v in parts.items())

    penalty = noise_penalty(title)
    base *= 1.0 - 0.55 * penalty

    # Damp live blogs rather than dropping them: the story is often real, but
    # its freshness is an artefact of the page being re-saved, not of anything
    # happening.
    if is_live_blog(title):
        base *= 0.62

    # A story carried by a lone low-authority outlet should not reach the top
    # of a morning briefing no matter how lurid the headline.
    if distinct_sources == 1 and max_authority < 0.7:
        base *= 0.72

    parts["noise"] = penalty
    return round(min(100.0, base * 100.0), 2), {k: round(v, 4) for k, v in parts.items()}


# Region multipliers applied at query time from the user's own weighting.
# 0 = hide entirely, 1 = neutral, 3 = strongly prefer.
def region_multiplier(weight: float) -> float:
    if weight <= 0:
        return 0.0
    return 0.55 + 0.45 * weight
