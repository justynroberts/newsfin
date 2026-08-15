"""Clustering behaviour.

These tests encode the two failure modes that actually matter, because both
were real bugs found by running the pipeline against live feeds:

  * Under-merging splits the day's biggest story into four medium ones and
    destroys the corroboration signal the whole ranking depends on.
  * Over-merging chains unrelated items together through a shared incidental
    token (a month name, a year) and produces nonsense clusters.
"""

from newsfin.pipeline import SUBGROUP_THRESHOLD, assign_subgroups, canonical_url, url_key
from newsfin.textutil import (
    IdfModel,
    entities,
    stem,
    token_set,
    trigrams,
)


def sim(idf, a, b):
    return idf.fuzzy(token_set(a), token_set(b), trigrams(a), trigrams(b))


def build_idf(titles):
    return IdfModel([token_set(t) for t in titles])


CORPUS = [
    "Powerful 7.7-magnitude earthquake kills at least 38 in Indonesia",
    "At least 20 killed as magnitude 7.7 quake hits Indonesia",
    "Bank of England holds interest rates at 4%",
    "Manchester United sack manager after third straight defeat",
    "Google Workspace Promo Codes: 14% Off for August 2026",
    "APOD: 2026 August 15 - Bright Perseids from Sweden",
    "Latest news bulletin | August 15th, 2026 - Morning",
    "Trump threatens to declare strait of Hormuz US territory",
    "Zelensky meets Macron in Paris for talks on Ukraine",
    "Five people killed in Northern Michigan shooting",
]


class TestSameStoryDetection:
    def test_differently_worded_reports_of_one_event_merge(self):
        idf = build_idf(CORPUS)
        score = sim(
            idf,
            "Powerful 7.7-magnitude earthquake kills at least 38 in Indonesia",
            "At least 20 killed as magnitude 7.7 quake hits Indonesia",
        )
        # Shares almost no surface wording; only IDF weighting plus the
        # quake/earthquake synonym gets these together.
        assert score >= 0.62, f"same event scored only {score:.3f}"

    def test_spelling_variants_of_a_name_still_match(self):
        idf = build_idf(CORPUS)
        score = sim(
            idf,
            "Zelensky arrives in Paris for talks with Macron",
            "Zelenskyy arrives in Paris for talks with Macron",
        )
        assert score >= 0.7, f"transliteration variant scored {score:.3f}"

    def test_unrelated_stories_sharing_a_date_do_not_merge(self):
        """The bug that chained WIRED coupon pages to NASA's picture of the day."""
        idf = build_idf(CORPUS)
        score = sim(
            idf,
            "Google Workspace Promo Codes: 14% Off for August 2026",
            "APOD: 2026 August 15 - Bright Perseids from Sweden",
        )
        assert score < 0.5, f"unrelated items scored {score:.3f}"

    def test_different_events_of_the_same_kind_stay_separate(self):
        idf = build_idf(CORPUS)
        score = sim(
            idf,
            "Powerful 7.7-magnitude earthquake kills at least 38 in Indonesia",
            "Earthquake hits Spanish city of Granada, damaging buildings",
        )
        assert score < 0.62, f"two different quakes merged at {score:.3f}"

    def test_same_words_different_subject_stays_separate(self):
        idf = build_idf(CORPUS)
        score = sim(
            idf,
            "Manchester United sack manager after third straight defeat",
            "Manchester City sign defender in record deal",
        )
        assert score < 0.62, f"different clubs merged at {score:.3f}"


class TestNormalisation:
    def test_stemming_unifies_verb_forms(self):
        assert stem("killed") == stem("kills") == "kill"
        assert stem("hits") == "hit"

    def test_dates_are_not_significant_tokens(self):
        assert "august" not in token_set("Flooding in August closes the M6")
        assert "2026" not in token_set("Budget 2026 raises income tax")

    def test_numbers_alone_are_dropped(self):
        assert not any(t.isdigit() for t in token_set("300 killed in 2026 crash"))

    def test_publisher_suffix_is_stripped(self):
        a = token_set("Bank holds rates steady - Reuters")
        b = token_set("Bank holds rates steady")
        assert a == b

    def test_leading_proper_noun_is_kept(self):
        """Dropping the first word split one airport closure into three stories.

        "Heathrow Airport pipe leak causes flood disruption" leads with the only
        token that identifies the story. Position is a bad proxy for
        significance; rarity is the real test, and it is applied at match time.
        """
        ents = entities("Heathrow Airport pipe leak causes flood disruption")
        assert "heathrow" in ents

    def test_common_leading_words_are_disqualified_by_rarity_not_position(self):
        idf = build_idf(CORPUS + ["Trump signs order", "Trump meets Putin", "Trump on tariffs"])
        # "trump" leads many headlines, so its weight is low...
        common = idf.weight("trump")
        # ...while a name appearing once is rare and therefore trusted.
        rare = idf.weight("perseids")
        assert rare > common

    def test_two_stories_about_one_person_do_not_merge_on_the_name_alone(self):
        idf = build_idf(CORPUS)
        score = sim(
            idf,
            "Trump announces sweeping new tariffs on imports",
            "Trump meets Putin for talks in Alaska",
        )
        assert score < 0.45, f"same subject, different events merged at {score:.3f}"


class TestSubgroups:
    def test_near_identical_headlines_share_an_angle(self):
        idf = build_idf(CORPUS)
        groups = assign_subgroups(
            [
                (1, "Luigi Mangione pleads guilty to federal stalking charges"),
                (2, "Luigi Mangione pleads guilty to federal stalking charge"),
            ],
            idf,
        )
        assert groups[1] == groups[2]

    def test_a_different_angle_gets_its_own_group(self):
        idf = build_idf(CORPUS)
        groups = assign_subgroups(
            [
                (1, "Luigi Mangione pleads guilty to federal stalking charges"),
                (2, "Watch: what happens if Luigi Mangione pleads guilty today?"),
                (3, "Who was Brian Thompson, the UnitedHealthcare chief executive?"),
            ],
            idf,
        )
        assert groups[3] != groups[1]

    def test_threshold_is_stricter_than_the_merge_threshold(self):
        # Sub-grouping partitions *within* a cluster, so it must be the
        # tighter of the two or every cluster becomes one angle.
        from newsfin.pipeline import MERGE_THRESHOLD

        assert SUBGROUP_THRESHOLD > MERGE_THRESHOLD


class TestUrlHandling:
    def test_tracking_parameters_are_stripped(self):
        a = canonical_url("https://bbc.co.uk/news/abc?at_medium=RSS&at_campaign=rss")
        assert a == "https://bbc.co.uk/news/abc"

    def test_meaningful_query_parameters_survive(self):
        url = "https://example.com/story?id=42"
        assert "id=42" in canonical_url(url)

    def test_scheme_and_trailing_slash_do_not_split_an_article(self):
        assert url_key("https://a.com/x/") == url_key("http://a.com/x")

    def test_fragment_is_dropped(self):
        assert canonical_url("https://a.com/x#comments") == "https://a.com/x"
