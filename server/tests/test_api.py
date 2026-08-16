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
    seed(1, "Powerful earthquake kills at least 38 in Indonesia", "world", 25, 92.0,
         source_name="BBC World")
    seed(2, "Bank of England holds interest rates at four percent", "uk", 12, 78.0,
         topics="business", source_name="BBC News")
    seed(3, "Trump threatens new tariffs on European imports", "us", 14, 76.0,
         topics="politics", source_name="NYT Politics")
    seed(4, "Council approves Salford housing development", "local", 2, 44.0,
         locales="manchester", source_name="Manchester Evening News")
    seed(5, "Macron calls snap election in France", "eu", 8, 70.0, topics="politics",
         source_name="Le Monde")
    seed(6, "Old story about a minor planning dispute", "uk", 1, 30.0, hours_ago=100,
         source_name="Local Gazette")
    # One prolific outlet filing a burst, all stamped the same minute - the
    # pattern that turned the lane into a feed reader for that publisher.
    for n in range(8, 14):
        seed(n, f"Burst filing number {n} from one newsroom", "world", 1, 20.0,
             hours_ago=0.5, source_name="Busy Wire")
    # Seeded last so it is unambiguously the newest, and deliberately low
    # impact: it should lead Latest and stay well down Top.
    seed(7, "Minor council notice filed this minute", "uk", 1, 22.0, hours_ago=0,
         source_name="Parish Notice Board")
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


class TestLatestLane:
    """`sort=latest` is a wire feed of the sources you already asked for."""

    def test_the_newest_story_leads(self):
        stories = get("/api/v1/headlines", sort="latest")["stories"]
        newest = max(s["published"] for s in stories)
        assert stories[0]["published"] == newest

    def test_distinct_outlets_stay_in_chronological_order(self):
        """Within the capped prefix - i.e. ignoring the deferred tail - the
        lane is strictly newest-first."""
        stories = get("/api/v1/headlines", sort="latest")["stories"]
        seen: set[str] = set()
        prefix = []
        for s in stories:
            if s["source"] in seen:
                break
            seen.add(s["source"])
            prefix.append(s["published"])
        assert prefix == sorted(prefix, reverse=True)

    def test_the_newest_story_leads_even_on_a_low_score(self):
        stories = get("/api/v1/headlines", sort="latest")["stories"]
        assert "this minute" in stories[0]["title"]

    def test_top_still_ranks_that_story_far_down(self):
        stories = get("/api/v1/headlines")["stories"]
        assert "this minute" not in stories[0]["title"]

    def test_filters_still_apply_in_the_latest_lane(self):
        stories = get("/api/v1/headlines", sort="latest", regions="world")["stories"]
        assert {s["region"] for s in stories} == {"world"}

    def test_a_hidden_region_stays_hidden_in_latest(self):
        stories = get(
            "/api/v1/headlines", sort="latest",
            weights="uk:0,world:2,us:2,eu:2,local:2,ie:2",
        )["stories"]
        assert "uk" not in {s["region"] for s in stories}

    def test_minimum_sources_still_applies(self):
        stories = get("/api/v1/headlines", sort="latest", min_sources=5)["stories"]
        assert all(s["sources"] >= 5 for s in stories)

    def test_the_ranking_still_travels_with_each_story(self):
        # The app keeps showing the impact marker and source count in this lane.
        story = get("/api/v1/headlines", sort="latest")["stories"][0]
        assert "impact" in story and "sources" in story

    def test_one_outlet_cannot_own_the_latest_lane(self):
        """A few outlets publish in bursts and stamp the whole burst with the
        same minute, so a purely chronological lane became a feed reader for
        that one publisher."""
        stories = get("/api/v1/headlines", sort="latest", limit=8)["stories"]
        from collections import Counter

        counts = Counter(s["source"] for s in stories)
        assert counts.most_common(1)[0][1] <= 2

    def test_deferred_stories_are_not_dropped(self):
        # Everything still appears, just later in the lane.
        stories = get("/api/v1/headlines", sort="latest", limit=200)["stories"]
        assert sum(1 for s in stories if s["source"] == "Busy Wire") == 6

    def test_paging_the_latest_lane_does_not_repeat(self):
        first = {s["id"] for s in get("/api/v1/headlines", sort="latest", limit=5)["stories"]}
        second = {
            s["id"]
            for s in get("/api/v1/headlines", sort="latest", limit=5, offset=5)["stories"]
        }
        assert not (first & second)

    def test_an_unknown_sort_is_rejected(self):
        assert client.get(
            "/api/v1/headlines", params={"sort": "sideways"}
        ).status_code == 422


class TestDiversify:
    """Exact semantics of the per-outlet cap, away from HTTP and SQL."""

    @staticmethod
    def rows(*sources):
        return [{"lead_source": s} for s in sources]

    def test_defers_rather_than_drops(self):
        from newsfin.api import _diversify

        out = _diversify(self.rows("A", "A", "A", "B"), per_source=2)
        assert [r["lead_source"] for r in out] == ["A", "A", "B", "A"]

    def test_keeps_relative_order_within_a_source(self):
        from newsfin.api import _diversify

        rows = [{"lead_source": "A", "n": i} for i in range(4)]
        out = _diversify(rows, per_source=1)
        assert [r["n"] for r in out] == [0, 1, 2, 3]

    def test_nothing_is_lost(self):
        from newsfin.api import _diversify

        rows = self.rows("A", "B", "A", "C", "A", "B")
        assert len(_diversify(rows, per_source=2)) == len(rows)

    def test_a_varied_page_is_left_untouched(self):
        from newsfin.api import _diversify

        rows = self.rows("A", "B", "C", "D")
        assert _diversify(rows, per_source=2) == rows


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
