# NewsFin

Impact-ranked world news. Headlines only, no pictures, straight through to the
article.

NewsFin polls ~330 RSS feeds from newsrooms across the UK, Ireland, Europe, the
US and the rest of the world, works out which of them are covering *the same
story*, and orders the result by how much it actually matters — not by how
recently it was published.

**Live:** https://newsfin.apps.fintonlabs.com

---

## Why the ranking works

The dominant signal is **corroboration**: how many independent newsrooms have
each decided, separately, that a story is worth their front page. That is a
real editorial vote aggregated across 330 outlets, and it is very hard to game.

A story's impact score blends:

| Signal | Weight | What it captures |
|---|---|---|
| Corroboration | 30% | Distinct newsrooms running it, log-scaled — 1→2 matters far more than 14→15 |
| Recency | 30% | 5-hour half-life, so the page turns over through the day |
| Authority | 14% | Blend of the best and the average outlet carrying it |
| Severity | 12% | Weighted lexicon — "killed" and "resigns" are not "wins" |
| Prominence | 7% | Position in the source feed; item 0 is that newsroom's lead |
| Velocity | 7% | How fast outlets are piling on — breaking vs slow-burn |

Corroboration and recency carry equal weight, tuned against a live snapshot:
at the original 38/18 the median age of the top fifteen was **9.2 hours** — the
front page was reliably yesterday. At 30/30 it is **2.9 hours**, and a
30-source earthquake still holds third place, which is the test that matters.
Pushing recency further was tried and rejected: it put a UFC result above the
earthquake, at which point the app is a wire feed rather than a ranking.

**Two lanes.** `Latest` is the default — strictly newest-first over your
filters, because the first question in the morning is what has happened since
last night. `Top` is the impact ranking, one tap away. Both cover the same
filtered set — a wire feed of the sources you actually asked for, capped at
two consecutive stories per newsroom so one prolific publisher cannot own it.

Commerce, puzzle answers and horoscopes are dropped at ingest. Feeds that
republish rather than report (Google News) count as a third of a newsroom.

Each reader then reweights it. Set Local and UK to *Top* and Europe to *Off*
and the same 330 feeds reorder around you — without burying a genuinely huge
World story.

## How stories get grouped

Grouping the same event across 330 differently-worded headlines is the whole
trick, and it runs in milliseconds — no embeddings, no model.

1. **Normalise** — strip accents, publisher suffixes, dates and bare numbers.
   Light stemming plus a synonym map so *quake* meets *earthquake*.
2. **IDF-weight the tokens** — *Indonesia* is evidence, *least* is not. Plain
   word overlap split one earthquake into four separate stories.
3. **Fuzzy match** — IDF token overlap blended with character-trigram overlap,
   so *Zelensky* still matches *Zelenskyy*. Either signal alone can carry the
   decision if it is overwhelming.
4. **Rare-entity assist** — a shared proper noun that appears in two clusters
   out of five thousand is near-conclusive. Scaled by rarity, so *Heathrow*
   merges three reports of one airport closure while *Trump* — which leads
   hundreds of unrelated headlines — merges nothing.
5. **Sub-group by angle** — inside a cluster, the live blog, the analysis and
   the local reaction are separated so the coverage sheet shows real variety.
6. **Consolidate** — a second pass sweeps together fragments seeded by
   different polls, so ordering never depends on which feed answered first.

Region comes from the **story text**, not the feed it arrived on: the
Guardian's UK edition runs Afghanistan coverage, and filing by feed buries the
UK tab under foreign reporting.

## The app

Flutter, iOS + Android + web from one codebase.

- **Headlines** — one blended list, reweighted by what you said matters.
- **Sections** — Local / UK / Ireland / Europe / US / World, each filterable by
  topic: Politics, Business, Tech, Science, Health, Climate, Sport,
  Entertainment, Culture, Security. Swipe between them.
- **Search** — full-text across everything from the last few days.
- **Coverage sheet** — long-press any story to see every outlet's headline for
  the same event. Nothing else shows you the framing side by side.
- **Learns what you read, on the device.** Opening a story is the signal; it
  compares how often you open a subject against how often it was *offered*, so
  it learns your taste rather than the shape of the feed. Two guarantees: the
  nudge is clamped so it can never leapfrog a genuinely bigger story, and a
  story carried by many independent newsrooms is never pushed down at all.
  Nothing is uploaded, Settings shows what it has learned, and one button
  erases it. It only touches the Top lane — Latest stays chronological.
- **Headline reader** — a spoken briefing for anyone who cannot comfortably
  read a phone screen. It reads the ranked list in order, announcing position,
  headline, outlet and source count, with 48px transport controls and speed
  settings. Hands-free, and it works on device or in the browser.
- Dark and light ("Paper") themes, reader-set text size, offline cache so it
  opens with content already on screen.

Design decisions and the archetype are recorded in [DESIGN.md](DESIGN.md).

## Running it

```bash
make setup     # server venv + dependencies
make ingest    # one full fetch/cluster/score pass (~45s, ~6,000 articles)
make dev       # API + PWA on :8099

make test      # 65 backend + 29 Flutter tests
make lint
make feeds     # re-check every registered feed is still alive
```

For the mobile app against a local server:

```bash
cd app && flutter run --dart-define=NEWSFIN_API=http://<your-lan-ip>:8099
```

`server/static/` is a **committed build artifact** — the compiled Flutter web
bundle. Deploys copy it straight into the image. Regenerate with `make web`
after changing anything under `app/lib/`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/headlines` | Ranked stories. `regions`, `topic`, `locale`, `weights`, `hours`, `min_sources`, `limit`, `offset` |
| `GET /api/v1/story/{id}` | One story with full coverage and the score breakdown |
| `GET /api/v1/search?q=` | Full-text search |
| `GET /api/v1/config` | Regions, topics, locales — the client renders its tabs from this |
| `GET /api/v1/sources` | Every feed with its live health record |
| `GET /api/v1/stats` | Cluster counts, failing feeds, last ingest |
| `GET /healthz` | Liveness |

`weights` is the personalisation hook: `?weights=uk:3,local:2,world:1.5,eu:0`.

## Deployment

Single container: FastAPI serves the JSON API and the PWA from one process,
with SQLite on a persistent volume. Breaking-news sources are polled every 3
minutes, the full set every 12, using ETag/Last-Modified so most polls cost a
304.

```bash
make docker-build && make docker-run
```

## How long articles are kept

| Stage | Window |
|---|---|
| Ingested | entries published in the last **4 days** |
| Retained | articles are pruned at **5 days**; a cluster dies with its last article |
| Story matching | a new headline is only compared against clusters from the last **72h** |
| Readable in the app | 12h / 24h / 48h / 4 days, set in Settings (API allows up to 5 days) |

Short on purpose. The ranking is built on corroboration, and an indefinitely
growing cluster would keep accumulating sources long after the story stopped
mattering — the retention window is what keeps those counts honest. It also
keeps the database to tens of megabytes.

## Feed health

Feeds rot constantly. `make feeds` fetches every registered URL and reports
which no longer parse; `GET /api/v1/stats` exposes the same thing at runtime. A
feed returning 200 with zero usable entries counts as dead, because it is.

---

MIT License - Copyright (c) fintonlabs.com
