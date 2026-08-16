"""HTTP API + static hosting for the Flutter web build."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import db
from .pipeline import refresh, source_keys_by_tier
from .scoring import region_multiplier
from .sources import (
    LOCALES,
    REGION_LABELS,
    REGIONS,
    SOURCES,
    TOPIC_LABELS,
    TOPICS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("newsfin.api")

FAST_MINUTES = int(os.environ.get("NEWSFIN_FAST_MINUTES", "3"))
FULL_MINUTES = int(os.environ.get("NEWSFIN_FULL_MINUTES", "12"))
STATIC_DIR = Path(os.environ.get("NEWSFIN_STATIC", "./static"))

scheduler = AsyncIOScheduler(timezone="UTC")
_refresh_lock = asyncio.Lock()


async def _guarded_refresh(tier: str):
    if _refresh_lock.locked():
        log.info("skip %s refresh - one already running", tier)
        return
    async with _refresh_lock:
        keys = source_keys_by_tier(tier) if tier != "all" else None
        try:
            await refresh(keys)
        except Exception:  # noqa: BLE001
            log.exception("%s refresh failed", tier)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    empty = db.connect().execute("SELECT COUNT(*) n FROM cluster").fetchone()["n"] == 0
    if empty:
        log.info("cold database - priming from every feed")
        asyncio.create_task(_guarded_refresh("all"))

    scheduler.add_job(_guarded_refresh, "interval", minutes=FAST_MINUTES,
                      args=["fast"], id="fast", max_instances=1, coalesce=True)
    scheduler.add_job(_guarded_refresh, "interval", minutes=FULL_MINUTES,
                      args=["all"], id="full", max_instances=1, coalesce=True)
    scheduler.start()
    log.info("scheduler up: fast=%dm full=%dm", FAST_MINUTES, FULL_MINUTES)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="NewsFin API",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# serialisation
# ----------------------------------------------------------------------

def _row_to_story(r, *, include_breakdown: bool = False) -> dict:
    out = {
        "id": r["id"],
        "title": r["lead_title"],
        "url": r["lead_url"],
        "source": r["lead_source"],
        "alt_title": r["summary"] or "",
        "region": r["region"],
        "regions": [x for x in (r["regions"] or "").split(",") if x],
        "topics": [x for x in (r["topics"] or "").split(",") if x],
        "locales": [x for x in (r["locales"] or "").split(",") if x],
        "published": r["published"],
        "sources": r["n_sources"],
        "impact": round(r["impact"], 1),
    }
    if "ranked" in r.keys():
        out["rank_score"] = round(r["ranked"], 1)
    if include_breakdown:
        try:
            out["breakdown"] = json.loads(r["breakdown"])
        except (TypeError, ValueError):
            out["breakdown"] = {}
    return out


def _diversify(rows: list, per_source: int = 2) -> list:
    """Stop one prolific outlet owning the top of the Latest lane.

    Takes rows in their existing order and defers any beyond `per_source` from
    the same newsroom, appending the deferred ones afterwards rather than
    dropping them. Nothing is lost, and the reader gets a spread of newsrooms
    at the point they actually look.
    """
    seen: dict[str, int] = {}
    kept, deferred = [], []
    for row in rows:
        outlet = row["lead_source"]
        count = seen.get(outlet, 0)
        if count < per_source:
            seen[outlet] = count + 1
            kept.append(row)
        else:
            deferred.append(row)
    return kept + deferred


def _coverage(cluster_ids: list[int]) -> dict[int, list[dict]]:
    if not cluster_ids:
        return {}
    marks = ",".join("?" * len(cluster_ids))
    rows = db.connect().execute(
        f"""SELECT cluster_id, source_name, title, url, published, authority
            FROM article WHERE cluster_id IN ({marks})
            ORDER BY cluster_id, authority DESC, published DESC""",
        cluster_ids,
    ).fetchall()
    out: dict[int, list[dict]] = {}
    for r in rows:
        bucket = out.setdefault(r["cluster_id"], [])
        if len(bucket) >= 8:
            continue
        if any(b["source"] == r["source_name"] for b in bucket):
            continue
        bucket.append({
            "source": r["source_name"],
            "title": r["title"],
            "url": r["url"],
            "published": r["published"],
        })
    return out


# ----------------------------------------------------------------------
# endpoints
# ----------------------------------------------------------------------

@app.get("/api/v1/config")
def config():
    """Everything the client needs to render its tabs without hardcoding."""
    return {
        "regions": [{"key": k, "label": REGION_LABELS[k]} for k in REGIONS],
        "topics": [{"key": k, "label": TOPIC_LABELS[k]} for k in TOPICS],
        "locales": [{"key": k, "label": v} for k, v in sorted(LOCALES.items(), key=lambda kv: kv[1])],
        "source_count": len(SOURCES),
        "default_weights": {"local": 1.5, "uk": 3.0, "ie": 0.5, "eu": 1.5, "us": 1.5, "world": 2.0},
    }


@app.get("/api/v1/headlines")
def headlines(
    regions: str | None = Query(None, description="comma list; omit for all"),
    topic: str | None = None,
    locale: str | None = None,
    weights: str | None = Query(None, description="e.g. uk:3,world:2,us:1,local:2,eu:1"),
    hours: int = Query(48, ge=1, le=120),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_sources: int = Query(1, ge=1, le=20),
    sort: str = Query("top", pattern="^(top|latest)$"),
    coverage: bool = True,
    debug: bool = False,
):
    """Ranked headlines.

    `weights` personalises the ordering: each cluster's impact is multiplied by
    the user's weight for its primary region, so someone who cares about Local
    and UK gets those lifted without losing a genuinely huge World story.

    `sort` picks the lane:

    * ``top``    - impact order. Recency is a third of that score, so this
                   still turns over through the day.
    * ``latest`` - strictly newest first. Every filter still applies, including
                   region weights of zero and `min_sources`, so it is a wire
                   feed of the sources you actually asked for rather than an
                   unfiltered firehose.
    """
    conn = db.connect()
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()

    where = ["published >= ?", "n_sources >= ?"]
    params: list = [cutoff, min_sources]

    wanted_regions = [r for r in (regions or "").split(",") if r] or None
    if wanted_regions:
        bad = [r for r in wanted_regions if r not in REGIONS]
        if bad:
            raise HTTPException(400, f"unknown region(s): {bad}")
        # Match the primary region only.
        #
        # The `regions` column lists every region whose feeds touched the
        # story, and matching against it leaked badly: a UK story picked up by
        # one American outlet appeared on the World tab, so World led with
        # British university news. Now that the primary region is derived from
        # the headline text rather than the feed, it is the honest answer to
        # "what is this story about" - and a section tab should mean exactly
        # that.
        clause = " OR ".join(["region = ?"] * len(wanted_regions))
        where.append(f"({clause})")
        params += wanted_regions

    if topic and topic != "top":
        if topic not in TOPICS:
            raise HTTPException(400, f"unknown topic: {topic}")
        where.append("(',' || topics || ',') LIKE ?")
        params.append(f"%,{topic},%")

    if locale:
        if locale not in LOCALES:
            raise HTTPException(400, f"unknown locale: {locale}")
        where.append("(',' || locales || ',') LIKE ?")
        params.append(f"%,{locale},%")

    weight_map: dict[str, float] = {}
    for pair in (weights or "").split(","):
        if ":" in pair:
            k, _, v = pair.partition(":")
            if k in REGIONS:
                try:
                    weight_map[k] = max(0.0, min(3.0, float(v)))
                except ValueError:
                    pass

    if weight_map:
        cases = " ".join(
            f"WHEN '{k}' THEN {region_multiplier(v):.4f}" for k, v in weight_map.items()
        )
        rank_expr = f"impact * (CASE region {cases} ELSE 1.0 END)"
        # weight 0 means "don't show me this at all"
        zeros = [k for k, v in weight_map.items() if v <= 0]
        if zeros:
            where.append("region NOT IN (" + ",".join("?" * len(zeros)) + ")")
            params += zeros
    else:
        rank_expr = "impact"

    # In the Latest lane the ranking still travels with each story - the app
    # keeps showing the impact marker and source count - but it no longer
    # decides the order. Impact breaks ties so two stories filed in the same
    # minute still lead with the bigger one.
    order_by = (
        "published DESC, ranked DESC" if sort == "latest" else "ranked DESC, published DESC"
    )

    sql = (
        f"SELECT *, {rank_expr} AS ranked FROM cluster "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {order_by} LIMIT ? OFFSET ?"
    )

    if sort == "latest":
        # Order alone is not enough here. A handful of outlets publish in
        # bursts and stamp the whole burst with the same minute, so a purely
        # chronological lane showed eight of its first ten from one newsroom -
        # a feed reader for that publisher, not the latest news.
        #
        # Diversify the whole prefix before slicing the page, so paging stays
        # consistent rather than re-deciding per page.
        window = min(600, offset + limit * 4)
        raw = conn.execute(sql, [*params, window, 0]).fetchall()
        rows = _diversify(raw, per_source=2)[offset : offset + limit]
    else:
        rows = conn.execute(sql, [*params, limit, offset]).fetchall()

    stories = [_row_to_story(r, include_breakdown=debug) for r in rows]
    if coverage and stories:
        cov = _coverage([s["id"] for s in stories])
        for s in stories:
            s["coverage"] = cov.get(s["id"], [])

    return {
        "count": len(stories),
        "generated_at": datetime.now(UTC).isoformat(),
        "last_ingest": db.get_meta("last_ingest", {}),
        "stories": stories,
    }


@app.get("/api/v1/story/{cluster_id}")
def story(cluster_id: int):
    row = db.connect().execute("SELECT * FROM cluster WHERE id=?", (cluster_id,)).fetchone()
    if not row:
        raise HTTPException(404, "no such story")
    out = _row_to_story(row, include_breakdown=True)
    out["coverage"] = _coverage([cluster_id]).get(cluster_id, [])
    return out


@app.get("/api/v1/search")
def search(q: str = Query(..., min_length=2), limit: int = Query(50, ge=1, le=200)):
    conn = db.connect()
    # Quote the term so FTS5 treats punctuation as text rather than syntax.
    term = '"' + q.replace('"', " ") + '"'
    try:
        rows = conn.execute(
            """SELECT c.*, c.impact AS ranked FROM cluster_fts f
               JOIN cluster c ON c.id = f.rowid
               WHERE cluster_fts MATCH ?
               ORDER BY c.impact DESC LIMIT ?""",
            (term, limit),
        ).fetchall()
    except Exception:  # noqa: BLE001 - malformed query should not 500
        rows = conn.execute(
            "SELECT *, impact AS ranked FROM cluster WHERE lead_title LIKE ? "
            "ORDER BY impact DESC LIMIT ?",
            (f"%{q}%", limit),
        ).fetchall()

    stories = [_row_to_story(r) for r in rows]
    cov = _coverage([s["id"] for s in stories])
    for s in stories:
        s["coverage"] = cov.get(s["id"], [])
    return {"query": q, "count": len(stories), "stories": stories}


@app.get("/api/v1/sources")
def sources():
    health = {
        r["source_key"]: dict(r)
        for r in db.connect().execute("SELECT * FROM feed_health").fetchall()
    }
    return {
        "count": len(SOURCES),
        "sources": [
            {
                "key": s.key, "name": s.name, "region": s.region,
                "topics": list(s.topics), "authority": s.authority,
                "locale": s.locale, "aggregator": s.aggregator,
                "health": health.get(s.key, {}),
            }
            for s in SOURCES
        ],
    }


@app.get("/api/v1/stats")
def stats():
    conn = db.connect()
    row = conn.execute(
        "SELECT COUNT(*) clusters, COALESCE(MAX(impact),0) top_impact FROM cluster"
    ).fetchone()
    arts = conn.execute("SELECT COUNT(*) n FROM article").fetchone()["n"]
    healthy = conn.execute(
        "SELECT COUNT(*) n FROM feed_health WHERE last_ok IS NOT NULL"
    ).fetchone()["n"]
    failing = conn.execute(
        "SELECT source_key, last_error, last_status FROM feed_health "
        "WHERE last_error != '' AND (last_ok IS NULL OR fail_count > ok_count) LIMIT 40"
    ).fetchall()
    return {
        "clusters": row["clusters"],
        "articles": arts,
        "top_impact": round(row["top_impact"], 1),
        "feeds_total": len(SOURCES),
        "feeds_healthy": healthy,
        "failing": [dict(r) for r in failing],
        "last_ingest": db.get_meta("last_ingest", {}),
    }


@app.post("/api/v1/refresh")
async def manual_refresh(tier: str = Query("fast", pattern="^(fast|all)$")):
    asyncio.create_task(_guarded_refresh(tier))
    return {"queued": tier}


@app.get("/healthz")
def healthz():
    n = db.connect().execute("SELECT COUNT(*) n FROM cluster").fetchone()["n"]
    return {"status": "ok", "clusters": n}


# ----------------------------------------------------------------------
# Flutter web build (PWA) - mounted last so it never shadows /api
# ----------------------------------------------------------------------

# A cold load pulls ~3.4MB gzipped, and the engine WASM alone is 2.2MB of it.
# Without cache headers the browser re-fetches all of it on every visit, which
# is the whole reason the app felt slow to open. These are the only files big
# enough to matter, and they change only when the Flutter SDK or the bundled
# fonts change - i.e. on a deliberate rebuild, not on a content update.
IMMUTABLE_PREFIXES = ("/canvaskit/", "/assets/", "/icons/")
IMMUTABLE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# Revalidated every load. They are small, and an ETag hit costs a 304 rather
# than a download - so a redeploy is picked up immediately without stranding
# anyone on a stale bundle.
REVALIDATE_PATHS = (
    "/",
    "/index.html",
    "/main.dart.js",
    "/flutter.js",
    "/flutter_bootstrap.js",
    "/flutter_service_worker.js",
    "/version.json",
    "/manifest.json",
)


@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path

    if path.startswith("/api/") or path == "/healthz":
        response.headers["Cache-Control"] = "no-store"
    elif any(path.startswith(p) for p in IMMUTABLE_PREFIXES):
        response.headers["Cache-Control"] = f"public, max-age={IMMUTABLE_MAX_AGE}, immutable"
    elif path in REVALIDATE_PATHS:
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    return response


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
    app.mount("/canvaskit", StaticFiles(directory=STATIC_DIR / "canvaskit"), name="canvaskit")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request):
        candidate = (STATIC_DIR / path).resolve()
        if path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            target = candidate
        else:
            target = STATIC_DIR / "index.html"

        # stat_result is what makes FileResponse populate etag/last-modified
        # up front. Without it those headers are only computed while the
        # response is being sent, so the conditional check below silently never
        # matched and every revalidation re-sent the whole file.
        response = FileResponse(target, stat_result=target.stat())

        # Honour conditional requests. StaticFiles does this for the mounted
        # trees, but a bare FileResponse does not - so every revalidation of
        # main.dart.js was answering with the whole 800KB bundle instead of a
        # 304. These files are must-revalidate, so that happened on every load.
        etag = response.headers.get("etag")
        if etag and etag in [
            t.strip() for t in (request.headers.get("if-none-match") or "").split(",")
        ]:
            return Response(status_code=304, headers={"etag": etag})

        return response
