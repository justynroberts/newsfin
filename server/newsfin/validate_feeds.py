"""Fetch every registered feed once and report which ones actually parse.

    python -m newsfin.validate_feeds            # human-readable table
    python -m newsfin.validate_feeds --json     # machine-readable

A feed counts as healthy only if it returns 2xx *and* feedparser finds at
least one entry with a title and a link. A 200 that yields zero entries is a
dead feed wearing a live badge, which is exactly the failure this catches.
"""

from __future__ import annotations

import asyncio
import json
import sys

import feedparser
import httpx

from .sources import SOURCES

UA = "NewsFinBot/1.0 (+https://newsfin.apps.fintonlabs.com)"


async def check(client: httpx.AsyncClient, source) -> dict:
    row = {"key": source.key, "name": source.name, "url": source.url, "ok": False, "entries": 0, "error": ""}
    try:
        r = await client.get(source.url, follow_redirects=True, timeout=20.0)
        row["status"] = r.status_code
        if r.status_code >= 400:
            row["error"] = f"HTTP {r.status_code}"
            return row
        parsed = feedparser.parse(r.content)
        usable = [e for e in parsed.entries if e.get("title") and e.get("link")]
        row["entries"] = len(usable)
        if not usable:
            row["error"] = "no usable entries"
            return row
        row["ok"] = True
    except Exception as exc:  # noqa: BLE001 - report, never abort the sweep
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


async def run() -> list[dict]:
    limits = httpx.Limits(max_connections=24)
    async with httpx.AsyncClient(headers={"User-Agent": UA}, limits=limits) as client:
        sem = asyncio.Semaphore(24)

        async def guarded(s):
            async with sem:
                return await check(client, s)

        return await asyncio.gather(*(guarded(s) for s in SOURCES))


def main() -> int:
    rows = asyncio.run(run())
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
    else:
        bad = [r for r in rows if not r["ok"]]
        good = [r for r in rows if r["ok"]]
        print(f"healthy: {len(good)}/{len(rows)}   articles seen: {sum(r['entries'] for r in good)}")
        if bad:
            print("\nFAILED")
            for r in sorted(bad, key=lambda r: r["key"]):
                print(f"  {r['key']:<24} {r['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
