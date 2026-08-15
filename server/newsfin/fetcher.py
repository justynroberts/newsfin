"""Feed fetching.

Two user agents: a polite bot string first, a browser string on retry. A
surprising number of outlets 403 one and serve the other, and which one works
flips over time - so we try both rather than hardcoding a guess.

Conditional requests (ETag / Last-Modified) are stored per feed, so a poll
every few minutes costs a 304 for most sources most of the time.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from .db import connect, tx
from .sources import SOURCES_BY_KEY, Source

log = logging.getLogger("newsfin.fetch")

BOT_UA = "NewsFinBot/1.0 (+https://newsfin.apps.fintonlabs.com)"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7"


@dataclass
class Item:
    source: Source
    title: str
    url: str
    summary: str
    published: datetime
    position: int


def _clean_summary(raw: str | None) -> str:
    if not raw:
        return ""
    import re

    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"&[a-z]+;|&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def _parse_date(entry) -> datetime:
    now = datetime.now(UTC)
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=UTC)
                # Feeds lie about the future; clamp so they can't hog the top.
                return min(dt, now)
            except (ValueError, TypeError):
                pass
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return min(dt.astimezone(UTC), now)
            except (TypeError, ValueError):
                pass
    return now


def _record_health(key: str, *, ok: bool, status: int | None, error: str, entries: int,
                   etag: str | None, modified: str | None) -> None:
    now = datetime.now(UTC).isoformat()
    with tx() as c:
        c.execute(
            """
            INSERT INTO feed_health(source_key,last_ok,last_error,last_status,ok_count,fail_count,
                                    last_entries,etag,modified)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_key) DO UPDATE SET
              last_ok     = CASE WHEN ?  THEN ? ELSE feed_health.last_ok END,
              last_error  = ?,
              last_status = ?,
              ok_count    = feed_health.ok_count   + ?,
              fail_count  = feed_health.fail_count + ?,
              last_entries= ?,
              etag        = COALESCE(?, feed_health.etag),
              modified    = COALESCE(?, feed_health.modified)
            """,
            (
                key, now if ok else None, error, status, 1 if ok else 0, 0 if ok else 1,
                entries, etag, modified,
                ok, now, error, status, 1 if ok else 0, 0 if ok else 1, entries, etag, modified,
            ),
        )


def _conditional_headers(key: str) -> dict[str, str]:
    row = connect().execute(
        "SELECT etag, modified FROM feed_health WHERE source_key=?", (key,)
    ).fetchone()
    h = {}
    if row:
        if row["etag"]:
            h["If-None-Match"] = row["etag"]
        if row["modified"]:
            h["If-Modified-Since"] = row["modified"]
    return h


async def fetch_one(client: httpx.AsyncClient, source: Source, *, max_age_days: int = 4) -> list[Item]:
    headers = {"Accept": ACCEPT, "Accept-Language": "en-GB,en;q=0.9"}
    headers.update(_conditional_headers(source.key))

    response = None
    last_error = ""
    for ua in (BOT_UA, BROWSER_UA):
        try:
            response = await client.get(
                source.url, headers={**headers, "User-Agent": ua},
                follow_redirects=True, timeout=30.0,
            )
            if response.status_code == 304:
                _record_health(source.key, ok=True, status=304, error="", entries=0,
                               etag=response.headers.get("etag"),
                               modified=response.headers.get("last-modified"))
                return []
            if response.status_code < 400:
                break
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001 - one bad feed must not stop the sweep
            last_error = f"{type(exc).__name__}: {exc}"
            response = None

    if response is None or response.status_code >= 400:
        _record_health(source.key, ok=False,
                       status=response.status_code if response else None,
                       error=last_error, entries=0, etag=None, modified=None)
        log.warning("feed failed %s: %s", source.key, last_error)
        return []

    parsed = feedparser.parse(response.content)
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

    items: list[Item] = []
    for i, entry in enumerate(parsed.entries[:80]):
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url or len(title) < 12:
            continue
        published = _parse_date(entry)
        if published < cutoff:
            continue
        items.append(
            Item(
                source=source,
                title=title,
                url=url,
                summary=_clean_summary(entry.get("summary") or entry.get("description")),
                published=published,
                position=i,
            )
        )

    _record_health(source.key, ok=True, status=response.status_code, error="",
                   entries=len(items),
                   etag=response.headers.get("etag"),
                   modified=response.headers.get("last-modified"))
    return items


async def fetch_all(keys: list[str] | None = None, concurrency: int = 20) -> list[Item]:
    targets = [SOURCES_BY_KEY[k] for k in keys] if keys else list(SOURCES_BY_KEY.values())
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(http2=False) as client:
        async def guarded(s: Source):
            async with sem:
                try:
                    return await fetch_one(client, s)
                except Exception as exc:  # noqa: BLE001
                    log.warning("fetch_one crashed for %s: %s", s.key, exc)
                    return []

        results = await asyncio.gather(*(guarded(s) for s in targets))

    return [item for batch in results for item in batch]
