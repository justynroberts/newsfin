"""Ingest: fetch -> dedupe -> cluster -> score -> persist.

Clustering uses a blocking index rather than an O(n^2) sweep. Each cluster is
indexed by its significant tokens; a new headline is only compared against
clusters that share at least one token. With ~8k articles and ~2k live
clusters that is a few hundred comparisons per article instead of millions.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

from . import geo, scoring
from .db import connect, prune, set_meta, tx
from .fetcher import Item, fetch_all
from .sources import SOURCES_BY_KEY
from .textutil import IdfModel, content_key, entities, token_set, trigrams

# Within a cluster, articles this similar are the *same angle* on the story
# (near-verbatim syndication or a straight rewrite). Below it they are a
# distinct angle worth showing as its own sub-group: the live blog, the
# analysis piece, the local reaction.
SUBGROUP_THRESHOLD = 0.74

log = logging.getLogger("newsfin.pipeline")

# Above this weighted-overlap score, two headlines are the same story.
MERGE_THRESHOLD = 0.62
# Between the floor and the threshold we merge only with corroborating
# evidence: a shared proper noun that is itself rare in the corpus.
ENTITY_ASSIST_THRESHOLD = 0.45
# Minimum IDF weight for a single shared proper noun to count as evidence.
# Below this the name is too common to identify a story - "Trump" leads
# hundreds of unrelated headlines a day and must never merge them.
ENTITY_RARITY_FLOOR = 4.0

_TRACKING = re.compile(r"^(utm_|ito$|ns_|cmp$|CMP$|at_|fbclid$|gclid$|smid$|ICID$)")


def canonical_url(url: str) -> str:
    """Strip tracking params so the same article from two feeds dedupes."""
    parts = urlsplit(url)
    if parts.query:
        kept = [
            kv for kv in parts.query.split("&")
            if kv and not _TRACKING.match(kv.split("=", 1)[0])
        ]
        parts = parts._replace(query="&".join(kept))
    parts = parts._replace(fragment="")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))


def url_key(url: str) -> str:
    c = canonical_url(url)
    return c[8:] if c.startswith("https://") else c[7:] if c.startswith("http://") else c


class ClusterIndex:
    """In-memory view of live clusters, rebuilt at the start of each ingest."""

    def __init__(self, window_hours: int = 72, corpus: list[frozenset[str]] | None = None):
        self.by_id: dict[int, dict] = {}
        self.postings: dict[str, set[int]] = defaultdict(set)
        cutoff = (datetime.now(UTC) - timedelta(hours=window_hours)).isoformat()
        rows = connect().execute(
            "SELECT id, lead_title, tokens, entities, published FROM cluster WHERE published >= ?",
            (cutoff,),
        ).fetchall()

        docs = [frozenset(r["tokens"].split()) for r in rows]
        # Seed IDF from the stored corpus plus this batch, so token rarity is
        # judged against the whole news day rather than one feed.
        self.idf = IdfModel(docs + list(corpus or []))

        for r, toks in zip(rows, docs, strict=True):
            self.by_id[r["id"]] = {
                "tokens": toks,
                "entities": frozenset(r["entities"].split()) if r["entities"] else frozenset(),
                "grams": trigrams(r["lead_title"]),
            }
            for t in toks:
                self.postings[t].add(r["id"])

    def add(self, cluster_id: int, toks: frozenset[str], ents: frozenset[str],
            grams: frozenset[str]) -> None:
        self.by_id[cluster_id] = {"tokens": toks, "entities": ents, "grams": grams}
        for t in toks:
            self.postings[t].add(cluster_id)

    def match(
        self, toks: frozenset[str], ents: frozenset[str], grams: frozenset[str],
        skip: set[int] | None = None,
    ) -> tuple[int | None, float]:
        """Best matching cluster and its confidence, or (None, 0.0).

        `skip` excludes clusters from consideration - used by the consolidation
        pass so a cluster cannot match itself or an already-merged fragment.
        """
        if not toks:
            return None, 0.0
        candidates: set[int] = set()
        # Only rare tokens are worth a posting-list lookup; a token shared by
        # hundreds of clusters ("says", "government") discriminates nothing.
        for t in toks:
            posting = self.postings.get(t)
            if posting and len(posting) < 400:
                candidates |= posting
        if not candidates:
            return None, 0.0

        if skip:
            candidates -= skip

        best_id, best_score = None, 0.0
        for cid in candidates:
            entry = self.by_id.get(cid)
            if not entry:
                continue
            sim = self.idf.fuzzy(toks, entry["tokens"], grams, entry["grams"])
            if sim < ENTITY_ASSIST_THRESHOLD:
                continue
            if sim < MERGE_THRESHOLD:
                shared = ents & entry["entities"]
                # A single shared *rare* proper noun (a named person, a place
                # nobody else is writing about today) is strong evidence.
                if not shared:
                    continue
                rare = max(self.idf.weight(e) for e in shared)
                if len(shared) < 2 and rare < ENTITY_RARITY_FLOOR:
                    continue
                # Scale with rarity rather than adding a flat bonus. "Heathrow"
                # at IDF 7.5 appears in two clusters out of five thousand and is
                # near-conclusive; a name at the 4.0 floor is merely suggestive.
                # A flat bonus left the genuine Heathrow merge at 0.614 against
                # a 0.62 bar - three reports of one airport closure, sitting as
                # three separate stories.
                sim += min(0.22, 0.10 + 0.035 * (rare - ENTITY_RARITY_FLOOR))
            if sim > best_score:
                best_id, best_score = cid, sim
        if best_score >= MERGE_THRESHOLD:
            return best_id, min(1.0, best_score)
        return None, 0.0


def assign_subgroups(titles: list[tuple[int, str]], idf: IdfModel) -> dict[int, int]:
    """Partition a cluster's articles into angles.

    Greedy agglomeration against each group's seed headline. Order is by
    authority (the caller sorts), so the most authoritative version of each
    angle becomes that sub-group's representative.

    Returns {article_id: subgroup_index}.
    """
    seeds: list[tuple[frozenset[str], frozenset[str]]] = []
    out: dict[int, int] = {}
    for art_id, title in titles:
        toks, grams = token_set(title), trigrams(title)
        best, best_sim = None, 0.0
        for i, (s_toks, s_grams) in enumerate(seeds):
            sim = idf.fuzzy(toks, s_toks, grams, s_grams)
            if sim > best_sim:
                best, best_sim = i, sim
        if best is not None and best_sim >= SUBGROUP_THRESHOLD:
            out[art_id] = best
        else:
            seeds.append((toks, grams))
            out[art_id] = len(seeds) - 1
    return out


def consolidate(index: ClusterIndex, max_merges: int = 400) -> int:
    """Second pass: merge clusters that are themselves the same story.

    Single-pass online clustering is order-dependent - a story seeded from one
    poll can end up beside a near-identical cluster seeded from an earlier one,
    which splits the corroboration count and pushes the day's biggest story
    down the page. This sweeps the fragments back together.

    Merges into the *larger* cluster so the surviving id is the one clients are
    most likely to already be holding.
    """
    ids = sorted(index.by_id)
    if len(ids) < 2:
        return 0

    conn = connect()
    sizes = {
        r["cluster_id"]: r["n"]
        for r in conn.execute(
            "SELECT cluster_id, COUNT(*) n FROM article GROUP BY cluster_id"
        ).fetchall()
    }

    merges: list[tuple[int, int]] = []  # (loser, winner)
    gone: set[int] = set()

    for cid in ids:
        if cid in gone or len(merges) >= max_merges:
            continue
        entry = index.by_id.get(cid)
        if not entry:
            continue
        other, score = index.match(entry["tokens"], entry["entities"], entry["grams"],
                                   skip=gone | {cid})
        if other is None or score < MERGE_THRESHOLD + 0.04:
            continue
        a, b = cid, other
        winner, loser = (a, b) if sizes.get(a, 1) >= sizes.get(b, 1) else (b, a)
        if loser in gone or winner in gone:
            continue
        merges.append((loser, winner))
        gone.add(loser)

    if not merges:
        return 0

    with tx() as c:
        for loser, winner in merges:
            c.execute("UPDATE article SET cluster_id=? WHERE cluster_id=?", (winner, loser))
            c.execute("DELETE FROM cluster WHERE id=?", (loser,))
            c.execute("DELETE FROM cluster_fts WHERE rowid=?", (loser,))
            index.by_id.pop(loser, None)

    log.info("consolidated %d fragment clusters", len(merges))
    return len(merges)


def _rescore_cluster(conn, cluster_id: int, idf: IdfModel | None = None) -> None:
    arts = conn.execute(
        "SELECT id, source_key, source_name, title, url, published, position, authority, aggregator,"
        "       region, topics, locale "
        "FROM article WHERE cluster_id=? ORDER BY authority DESC, position ASC",
        (cluster_id,),
    ).fetchall()
    if not arts:
        return

    if idf is not None and len(arts) > 1:
        groups = assign_subgroups([(a["id"], a["title"]) for a in arts], idf)
        conn.executemany(
            "UPDATE article SET subgroup=? WHERE id=?",
            [(g, aid) for aid, g in groups.items()],
        )
        n_angles = len(set(groups.values()))
    else:
        n_angles = 1

    by_source = {}
    for a in arts:
        # One vote per newsroom, not per feed - BBC News and BBC Politics
        # carrying the same story is one outlet, not two.
        outlet = a["source_key"].split("-")[0]
        prev = by_source.get(outlet)
        if prev is None or a["authority"] > prev["authority"]:
            by_source[outlet] = a

    distinct = len(by_source)
    aggregators = sum(1 for a in by_source.values() if a["aggregator"])
    authorities = [a["authority"] for a in by_source.values()]
    max_auth = max(authorities)
    mean_auth = sum(authorities) / len(authorities)
    best_pos = min(a["position"] for a in arts)

    published_times = [datetime.fromisoformat(a["published"]) for a in arts]
    published = max(published_times)
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    last_hour = len({
        a["source_key"].split("-")[0]
        for a in arts
        if datetime.fromisoformat(a["published"]) >= hour_ago
    })

    # The lead article is the version the user reads and the link they follow.
    # Authority drives the choice, but a headline that is a video promo or a
    # question ("Watch: what happens if X pleads guilty?") loses to a plain
    # statement of the news from a slightly less authoritative outlet.
    def lead_rank(a) -> float:
        return a["authority"] * (1.0 - 0.5 * scoring.lead_penalty(a["title"])) - a["position"] * 0.002

    lead = max(arts, key=lead_rank)

    topics = sorted({t for a in arts for t in (a["topics"] or "").split(",") if t})

    # Region comes from what the story is *about*, not the feed it arrived on.
    # National outlets publish the world on their home feeds, so filing by feed
    # buries the UK tab under foreign reporting.
    #
    # Every headline in the cluster gets a vote, which makes the reading far
    # more robust than any single headline: ten outlets naming Indonesia
    # outweigh one that only said "quake kills 38".
    region_counts: dict[str, float] = defaultdict(float)
    for a in arts:
        resolved = geo.resolve_region(a["title"], a["region"] or "world")
        region_counts[resolved] += a["authority"]

    primary = (
        max(region_counts.items(), key=lambda kv: (kv[1], kv[0] == "local"))[0]
        if region_counts
        else "world"
    )
    regions = sorted(region_counts)

    # Locale only applies to UK-facing stories; a Birmingham, Alabama shooting
    # must not appear on the West Midlands tab.
    locales_found: set[str] = set()
    if primary in ("local", "uk"):
        local_outlets, national_outlets = set(), set()
        for a in arts:
            outlet = a["source_key"].split("-")[0]
            if a["locale"]:
                locales_found.add(a["locale"])
                local_outlets.add(outlet)
            else:
                national_outlets.add(outlet)
            found = geo.detect_locale(a["title"])
            if found:
                locales_found.add(found)

        # Promote to Local only when regional newsrooms are the *main* carriers.
        # National stories get picked up by local papers too - if the BBC, Sky
        # and the Guardian are all running it, it is national news no matter how
        # many regional titles also carried it.
        if primary == "uk" and local_outlets and len(local_outlets) >= len(national_outlets):
            primary = "local"
            regions = sorted(set(regions) | {"local"})
    locales = sorted(locales_found)

    impact, breakdown = scoring.impact(
        distinct_sources=distinct,
        aggregator_sources=aggregators,
        max_authority=max_auth,
        mean_authority=mean_auth,
        published=published,
        title=lead["title"],
        best_position=best_pos,
        sources_last_hour=last_hour,
    )

    body = conn.execute(
        "SELECT title FROM article WHERE cluster_id=? AND url_key != ? LIMIT 1",
        (cluster_id, url_key(lead["url"])),
    ).fetchone()
    alt = body["title"] if body else ""

    conn.execute(
        """UPDATE cluster SET lead_title=?, lead_url=?, lead_source=?, summary=?,
               region=?, regions=?, topics=?, locales=?, published=?, last_update=?,
               n_sources=?, n_aggregators=?, n_angles=?, max_authority=?, mean_authority=?,
               best_position=?, impact=?, breakdown=?
           WHERE id=?""",
        (
            lead["title"], lead["url"], lead["source_name"], alt,
            primary, ",".join(regions), ",".join(topics), ",".join(locales),
            published.isoformat(), datetime.now(UTC).isoformat(),
            distinct, aggregators, n_angles, max_auth, mean_auth, best_pos,
            impact, json.dumps(breakdown), cluster_id,
        ),
    )
    conn.execute("DELETE FROM cluster_fts WHERE rowid=?", (cluster_id,))
    conn.execute(
        "INSERT INTO cluster_fts(rowid, lead_title, summary) VALUES(?,?,?)",
        (cluster_id, lead["title"], alt),
    )


def ingest(items: list[Item]) -> dict:
    started = time.monotonic()
    conn = connect()
    # Give the IDF model this batch up front so token rarity is judged against
    # the whole news day, not just what is already stored.
    index = ClusterIndex(corpus=[token_set(i.title) for i in items])

    existing = {
        r["url_key"] for r in conn.execute("SELECT url_key FROM article").fetchall()
    }
    seen_content: dict[str, int] = {}

    new_articles = 0
    new_clusters = 0
    merged = 0
    skipped_junk = 0
    confidences: list[float] = []
    touched: set[int] = set()

    # Newest first so the strongest version of a story seeds its cluster.
    items = sorted(items, key=lambda i: (-i.source.authority, i.position))

    with tx() as c:
        for item in items:
            uk = url_key(item.url)
            if uk in existing:
                continue
            if scoring.is_junk(item.title):
                skipped_junk += 1
                continue

            toks = token_set(item.title)
            if len(toks) < 3:
                continue
            ents = entities(item.title)

            grams = trigrams(item.title)
            ckey = content_key(item.title)
            cluster_id = seen_content.get(ckey)
            confidence = 1.0
            if cluster_id is None:
                cluster_id, confidence = index.match(toks, ents, grams)

            if cluster_id is None:
                cur = c.execute(
                    """INSERT INTO cluster(lead_title, lead_url, lead_source, tokens, entities,
                                           region, first_seen, published, last_update)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        item.title, item.url, item.source.name,
                        " ".join(sorted(toks)), " ".join(sorted(ents)),
                        item.source.region,
                        datetime.now(UTC).isoformat(),
                        item.published.isoformat(),
                        datetime.now(UTC).isoformat(),
                    ),
                )
                cluster_id = cur.lastrowid
                index.add(cluster_id, toks, ents, grams)
                new_clusters += 1
            else:
                merged += 1
                confidences.append(confidence)

            seen_content[ckey] = cluster_id

            c.execute(
                """INSERT OR IGNORE INTO article(cluster_id, source_key, source_name, title, url,
                       url_key, published, position, authority, aggregator, region, topics, locale)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cluster_id, item.source.key, item.source.name, item.title, item.url, uk,
                    item.published.isoformat(), item.position, item.source.authority,
                    1 if item.source.aggregator else 0, item.source.region,
                    ",".join(item.source.topics), item.source.locale,
                ),
            )
            existing.add(uk)
            new_articles += 1
            touched.add(cluster_id)

    # Sweep fragments together before scoring, so corroboration counts reflect
    # the consolidated story rather than the order feeds happened to arrive in.
    consolidated = consolidate(index)

    # Rescore everything recent, not just what changed: recency decay means a
    # cluster nobody touched still needs its impact refreshed.
    cutoff = (datetime.now(UTC) - timedelta(hours=72)).isoformat()
    stale = [
        r["id"] for r in conn.execute(
            "SELECT id FROM cluster WHERE published >= ?", (cutoff,)
        ).fetchall()
    ]
    with tx() as c:
        for cid in set(stale) | touched:
            _rescore_cluster(c, cid, index.idf)

    removed = prune()
    elapsed = round(time.monotonic() - started, 2)
    stats = {
        "fetched": len(items),
        "new_articles": new_articles,
        "new_clusters": new_clusters,
        "merged": merged,
        "consolidated": consolidated,
        "skipped_junk": skipped_junk,
        "mean_merge_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        "rescored": len(set(stale) | touched),
        "pruned": removed,
        "seconds": elapsed,
        "at": datetime.now(UTC).isoformat(),
    }
    set_meta("last_ingest", stats)
    log.info("ingest %s", stats)
    return stats


async def refresh(keys: list[str] | None = None) -> dict:
    items = await fetch_all(keys)
    return ingest(items)


def source_keys_by_tier(tier: str) -> list[str]:
    """Fast tier = the outlets that break news; polled far more often."""
    fast = {
        "bbc-top", "bbc-uk", "bbc-world", "bbc-politics", "bbc-business",
        "sky-home", "sky-uk", "sky-world", "sky-politics",
        "guardian-uk", "guardian-world", "guardian-politics",
        "nyt-home", "nyt-world", "npr-news", "cnn-top", "cnn-world",
        "cbs-main", "abc-top", "nbc-top", "aljazeera", "reuters-top",
        "independent-uk", "standard-news", "axios", "politico-us", "politico-eu",
        "dw-top", "france24", "euronews", "cbc-top", "ft-home", "semafor",
    }
    if tier == "fast":
        return [k for k in fast if k in SOURCES_BY_KEY]
    return [k for k in SOURCES_BY_KEY if k not in fast]
