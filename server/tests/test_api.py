"""API behaviour, against a database seeded with known clusters.

The endpoint contract matters as much as the ranking: the app renders its tabs
straight from these responses, so a section returning the wrong region is a
visible product bug, not an internal detail.
"""

import os
import tempfile
from datetime import UTC, datetime, timedelta

import pytest

# The DB path is read at import time, so it has to be set before newsfin.db is
# imported by anything else.
_tmp = tempfile.mkdtemp()
os.environ["NEWSFIN_DB"] = os.path.join(_tmp, "test.db")
os.environ["NEWSFIN_STATIC"] = os.path.join(_tmp, "no-static")

from fastapi.testclient import TestClient  # noqa: E402

from newsfin import db  # noqa: E402
from newsfin.api import app  # noqa: E402


def seed(cluster_id, title, region, sources, impact, *, topics="top",
         locales="", hours_ago=1, source_name="BBC News"):
    now = datetime.now(UTC)
    published = (now - timedelta(hours=hours_ago)).isoformat()
    with db.tx() as c:
        c.execute(
            """INSERT INTO cluster(id, lead_title, lead_url, lead_source, summary, tokens,
                   entities, region, regions, topics, locales, first_seen, published,
                   last_update, n_sources, n_aggregators, max_authority, mean_authority,
                   best_position, impact, breakdown)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cluster_id, title, f"https://example.com/{cluster_id}", source_name, "",
             title.lower(), "", region, f"{region},world", topics, locales,
             published, published, published, sources, 0, 0.9, 0.9, 0, impact, "{}"),
        )
        c.execute(
            "INSERT INTO cluster_fts(rowid, lead_title, summary) VALUES(?,?,?)",
            (cluster_id, title, ""),
        )
        for i in range(sources):
            c.execute(
                """INSERT INTO article(cluster_id, source_key, source_name, title, url,
                       url_key, published, position, authority, aggregator, region, topics, locale)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cluster_id, f"src{i}", f"Outlet {i}", title, f"https://o{i}.com/{cluster_id}",
                 f"o{i}.com/{cluster_id}", published, i, 0.9, 0, region, topics, locales or None),
            )


@pytest.fixture(scope="module", autouse=True)
def seeded():
    conn = db.connect()
    conn.executescript(
        "DELETE FROM article; DELETE FROM cluster; DELETE FROM cluster_fts; DELETE FROM meta;"
    )
    seed(1, "Powerful earthquake kills at least 38 in Indonesia", "world", 25, 92.0)
    seed(2, "Bank of England holds interest rates at four percent", "uk", 12, 78.0,
         topics="business")
    seed(3, "Trump threatens new tariffs on European imports", "us", 14, 76.0,
         topics="politics")
    seed(4, "Council approves Salford housing development", "local", 2, 44.0,
         locales="manchester")
    seed(5, "Macron calls snap election in France", "eu", 8, 70.0, topics="politics")
    seed(6, "Old story about a minor planning dispute", "uk", 1, 30.0, hours_ago=100)
    yield
    conn.executescript("DELETE FROM article; DELETE FROM cluster; DELETE FROM cluster_fts;")


# Constructed WITHOUT the `with` form on purpose: entering the context manager
# runs the lifespan, which starts the poll scheduler and primes from the live
# internet. Plain construction exercises the real HTTP layer - query parsing,
# validation, status codes - with none of that.
client = TestClient(app)


def get(path, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
    return r.json()


class TestHeadlines:
    def test_returns_stories_ranked_by_impact(self):
        out = get("/api/v1/headlines")
        impacts = [s["impact"] for s in out["stories"]]
        assert impacts == sorted(impacts, reverse=True)
        assert out["stories"][0]["sources"] == 25

    def test_a_section_returns_only_that_region(self):
        """The World tab once led with British university news.

        The region filter also matched every region whose feeds had touched a
        story, so anything an American outlet picked up appeared under World.
        """
        out = get("/api/v1/headlines", regions="world")
        assert out["count"] >= 1
        assert {s["region"] for s in out["stories"]} == {"world"}

    def test_each_region_is_isolated(self):
        for region in ["uk", "us", "eu", "local"]:
            out = get("/api/v1/headlines", regions=region)
            assert {s["region"] for s in out["stories"]} == {region}, region

    def test_unknown_region_is_rejected(self):
        assert client.get("/api/v1/headlines", params={"regions": "atlantis"}).status_code == 400

    def test_topic_filter_narrows_the_list(self):
        out = get("/api/v1/headlines", topic="business")
        assert all("business" in s["topics"] for s in out["stories"])

    def test_time_window_excludes_stale_stories(self):
        titles = [s["title"] for s in get("/api/v1/headlines", hours=24)["stories"]]
        assert not any("minor planning dispute" in t for t in titles)

    def test_minimum_sources_filters_single_source_chatter(self):
        out = get("/api/v1/headlines", min_sources=5)
        assert all(s["sources"] >= 5 for s in out["stories"])

    def test_weighting_reorders_the_list(self):
        # Unweighted, the 25-source earthquake leads.
        assert get("/api/v1/headlines")["stories"][0]["region"] == "world"
        # A reader who only cares about the UK sees the UK story first.
        weighted = get("/api/v1/headlines", weights="uk:3,world:0.4,us:0.4,eu:0.4,local:0.4")
        assert weighted["stories"][0]["region"] == "uk"

    def test_zero_weight_hides_a_region_entirely(self):
        out = get("/api/v1/headlines", weights="world:0,uk:2,us:2,eu:2,local:2,ie:2")
        assert "world" not in {s["region"] for s in out["stories"]}

    def test_coverage_is_attached_for_the_app(self):
        out = get("/api/v1/headlines", limit=3)
        assert all("coverage" in s for s in out["stories"])
        assert out["stories"][0]["coverage"]

    def test_paging_does_not_repeat_stories(self):
        first = {s["id"] for s in get("/api/v1/headlines", limit=2, offset=0)["stories"]}
        second = {s["id"] for s in get("/api/v1/headlines", limit=2, offset=2)["stories"]}
        assert not (first & second)


class TestSearch:
    def test_finds_a_story_by_word(self):
        out = get("/api/v1/search", q="earthquake")
        assert out["count"] >= 1
        assert "Indonesia" in out["stories"][0]["title"]

    def test_no_matches_is_an_empty_list_not_an_error(self):
        assert get("/api/v1/search", q="zzzznotathing")["count"] == 0

    def test_punctuation_does_not_break_the_query(self):
        """FTS5 treats bare punctuation as syntax; unquoted it raised a 500."""
        assert get("/api/v1/search", q='rates "at" four')["count"] >= 0


class TestMetadata:
    def test_config_describes_every_tab_the_app_renders(self):
        out = get("/api/v1/config")
        keys = {r["key"] for r in out["regions"]}
        assert keys == {"local", "uk", "ie", "eu", "us", "world"}
        assert out["source_count"] > 200
        assert set(out["default_weights"]) == keys

    def test_story_detail_includes_the_score_breakdown(self):
        out = get("/api/v1/story/1")
        assert out["sources"] == 25
        assert "breakdown" in out

    def test_missing_story_is_a_404(self):
        assert client.get("/api/v1/story/999999").status_code == 404

    def test_stats_reports_feed_health(self):
        out = get("/api/v1/stats")
        assert out["feeds_total"] > 200
        assert out["clusters"] >= 6

    def test_healthz(self):
        assert get("/healthz")["status"] == "ok"
