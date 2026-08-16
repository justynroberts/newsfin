"""Ranking behaviour.

The ordering promise of this app is "most impact first". These tests pin the
comparisons that promise implies, rather than asserting exact scores - the
weights are tunable, the orderings are not.
"""

from datetime import UTC, datetime, timedelta

from newsfin import geo, scoring


def impact(**kwargs) -> float:
    base = dict(
        distinct_sources=1,
        aggregator_sources=0,
        max_authority=0.8,
        mean_authority=0.8,
        published=datetime.now(UTC) - timedelta(minutes=30),
        title="Something happened somewhere today",
        best_position=3,
        sources_last_hour=1,
    )
    base.update(kwargs)
    return scoring.impact(**base)[0]


class TestCorroborationDominates:
    def test_more_newsrooms_outrank_fewer(self):
        assert impact(distinct_sources=15) > impact(distinct_sources=2)

    def test_widely_covered_older_story_beats_a_fresh_single_source(self):
        """The core claim: impact, not recency, drives the order."""
        big_and_older = impact(
            distinct_sources=20,
            published=datetime.now(UTC) - timedelta(hours=6),
            sources_last_hour=0,
        )
        small_and_fresh = impact(
            distinct_sources=1,
            published=datetime.now(UTC),
            sources_last_hour=1,
        )
        assert big_and_older > small_and_fresh

    def test_gains_flatten_as_sources_pile_up(self):
        first = impact(distinct_sources=3) - impact(distinct_sources=1)
        later = impact(distinct_sources=20) - impact(distinct_sources=18)
        assert first > later

    def test_aggregators_count_for_less_than_newsrooms(self):
        real = impact(distinct_sources=6, aggregator_sources=0)
        mostly_aggregated = impact(distinct_sources=6, aggregator_sources=5)
        assert real > mostly_aggregated


class TestQuality:
    def test_authority_breaks_ties(self):
        assert impact(max_authority=0.95, mean_authority=0.95) > impact(
            max_authority=0.5, mean_authority=0.5
        )

    def test_lone_low_trust_source_is_held_back(self):
        assert impact(distinct_sources=1, max_authority=0.5, mean_authority=0.5) < impact(
            distinct_sources=1, max_authority=0.95, mean_authority=0.95
        )

    def test_severity_lifts_consequential_news(self):
        assert impact(title="Earthquake kills at least 200 in coastal city") > impact(
            title="Council approves new cycle lane consultation"
        )

    def test_keyword_stuffing_saturates(self):
        stuffed = scoring.severity_score(
            "war crisis emergency killed dead attack nuclear disaster"
        )
        assert stuffed <= 1.0

    def test_commerce_is_pushed_down(self):
        assert impact(title="Best gift deals and discount codes this weekend") < impact(
            title="Government announces new housing policy"
        )

    def test_lead_position_in_a_feed_counts(self):
        assert impact(best_position=0) > impact(best_position=40)


class TestRecencyCarriesRealWeight:
    """Recency is a third of the score, not a tie-breaker.

    At the original 0.18/7h the median age of the top fifteen was over nine
    hours - the front page was reliably yesterday's news.
    """

    def test_recency_matters_as_much_as_corroboration(self):
        assert scoring.WEIGHTS["recency"] == scoring.WEIGHTS["corroboration"]

    def test_a_few_hours_old_is_clearly_behind_fresh(self):
        fresh = impact(distinct_sources=4, published=datetime.now(UTC))
        stale = impact(
            distinct_sources=4, published=datetime.now(UTC) - timedelta(hours=10)
        )
        # Not a rounding difference - a visible gap.
        assert fresh - stale > 8

    def test_yesterdays_story_needs_far_more_coverage_to_hold_the_top(self):
        yesterday_big = impact(
            distinct_sources=20,
            published=datetime.now(UTC) - timedelta(hours=20),
            sources_last_hour=0,
        )
        today_moderate = impact(
            distinct_sources=5,
            published=datetime.now(UTC) - timedelta(hours=1),
            sources_last_hour=2,
        )
        assert today_moderate > yesterday_big


class TestRecency:
    def test_newer_wins_all_else_equal(self):
        assert impact(published=datetime.now(UTC)) > impact(
            published=datetime.now(UTC) - timedelta(hours=12)
        )

    def test_overnight_news_survives_until_breakfast(self):
        """An 11pm story must still be findable at 7am. With a 5h half-life it
        is well down the decay curve, so it has to earn its place on
        corroboration - which is the intended trade."""
        assert scoring.recency_score(datetime.now(UTC) - timedelta(hours=8)) > 0.25

    def test_future_dates_do_not_win(self):
        assert scoring.recency_score(datetime.now(UTC) + timedelta(hours=5)) <= 1.0


class TestJunkFilter:
    def test_promo_and_puzzle_content_is_rejected(self):
        for title in [
            "Bose Promo Code: 40% Off for August 2026",
            "HelloFresh Promo Codes: 55% Off",
            "Wordle today: the answer and hints for puzzle 1234",
            "Your horoscope for the week ahead",
            "APOD: 2026 August 15 - Bright Perseids",
        ]:
            assert scoring.is_junk(title), title

    def test_real_news_is_kept(self):
        for title in [
            "Bank of England holds interest rates at 4%",
            "At least 38 dead after earthquake strikes Indonesia",
            "Government wins vote on welfare reform",
            "Off-duty officer praised for river rescue",
        ]:
            assert not scoring.is_junk(title), title


class TestLeadSelection:
    def test_video_promos_are_poor_leads(self):
        assert scoring.lead_penalty("Watch: what happens next?") > scoring.lead_penalty(
            "Mangione pleads guilty to federal stalking charges"
        )

    def test_plain_statements_are_unpenalised(self):
        assert scoring.lead_penalty(
            "Bank of England holds interest rates at four percent"
        ) == 0.0


class TestRegionWeighting:
    def test_zero_weight_hides_a_region(self):
        assert scoring.region_multiplier(0) == 0.0

    def test_higher_weight_lifts_a_region(self):
        assert scoring.region_multiplier(3) > scoring.region_multiplier(1)

    def test_weighting_can_reorder_two_stories(self):
        world_story = 80.0 * scoring.region_multiplier(1.0)
        local_story = 60.0 * scoring.region_multiplier(3.0)
        assert local_story > world_story


class TestGeography:
    def test_foreign_reporting_leaves_the_uk_tab(self):
        """A UK-edition feed carrying Afghanistan coverage is not UK news."""
        assert geo.resolve_region(
            "Five years into Taliban rule, Afghanistan plunges into collapse", "uk"
        ) == "world"

    def test_genuine_uk_news_stays(self):
        assert geo.resolve_region("Bank of England holds interest rates", "uk") == "uk"

    def test_us_politics_is_filed_as_us(self):
        assert geo.resolve_region("Trump threatens new tariffs on imports", "world") == "us"

    def test_european_stories_are_filed_as_eu(self):
        assert geo.resolve_region("Macron calls snap election in France", "world") == "eu"

    def test_headline_without_geography_keeps_its_feed(self):
        assert geo.resolve_region("Man charged after fatal collision", "local") == "local"

    def test_uk_place_names_resolve_to_an_area(self):
        assert geo.detect_locale("Man dies after crash on M60 in Salford") == "manchester"
        assert geo.detect_locale("Cardiff council approves budget") == "wales"

    def test_ambiguous_headlines_do_not_flip_region(self):
        # Names both a UK and an EU entity - too close to call, keep the feed.
        assert geo.resolve_region(
            "UK and Germany sign new defence agreement", "uk"
        ) == "uk"


class TestUndatedEntries:
    """About 2% of entries arrive with no usable timestamp.

    Stamping those with the fetch time told the ranking they had just broken,
    and they monopolised both the Top and Latest lanes.
    """

    def test_an_undated_entry_inherits_the_oldest_date_in_its_feed(self):
        from newsfin.fetcher import _undated_fallback

        now = datetime.now(UTC)
        dated = [now - timedelta(hours=1), now - timedelta(hours=9)]
        assert _undated_fallback(dated) == now - timedelta(hours=9)

    def test_a_wholly_undated_feed_does_not_claim_to_be_breaking(self):
        from newsfin.fetcher import _undated_fallback

        assert (datetime.now(UTC) - _undated_fallback([])) >= timedelta(hours=11)

    def test_an_undated_entry_scores_below_a_genuinely_fresh_one(self):
        from newsfin.fetcher import _undated_fallback

        undated = impact(distinct_sources=3, published=_undated_fallback([]))
        fresh = impact(distinct_sources=3, published=datetime.now(UTC))
        assert fresh > undated
