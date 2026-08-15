"""Curated feed registry.

Every entry is a real, publicly reachable RSS/Atom endpoint. Fields:

    key         stable slug, used as the DB primary key and in the API
    name        display name shown on a headline row
    url         feed URL
    region      one of REGIONS - the geographic lane the feed belongs to
    topics      zero or more topic slugs; drives the topic tabs
    authority   0.0-1.0 editorial weight. Wire services and public
                broadcasters sit high, tabloids and aggregators low. This is
                deliberately opinionated: it is the tie-breaker when two
                stories have identical corroboration.
    locale      for region="local", the UK sub-area slug the user can pick
    aggregator  True for Google News style meta-feeds. They inflate
                corroboration counts without adding an independent newsroom,
                so scoring discounts them.

Run `python -m newsfin.validate_feeds` to re-check every URL; dead feeds are
pruned there, not silently tolerated at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REGIONS = ["local", "uk", "ie", "eu", "us", "world"]

REGION_LABELS = {
    "local": "Local",
    "uk": "UK",
    "ie": "Ireland",
    "eu": "Europe",
    "us": "US",
    "world": "World",
}

TOPICS = [
    "top",
    "politics",
    "business",
    "tech",
    "science",
    "health",
    "environment",
    "sport",
    "culture",
    "security",
]

TOPIC_LABELS = {
    "top": "Top",
    "politics": "Politics",
    "business": "Business",
    "tech": "Tech",
    "science": "Science",
    "health": "Health",
    "environment": "Climate",
    "sport": "Sport",
    "culture": "Culture",
    "security": "Security",
}

# UK sub-areas offered on the Local tab.
LOCALES = {
    "london": "London",
    "manchester": "Greater Manchester",
    "liverpool": "Merseyside",
    "birmingham": "West Midlands",
    "leeds": "West Yorkshire",
    "sheffield": "South Yorkshire",
    "newcastle": "North East",
    "bristol": "Bristol & West",
    "nottingham": "Nottinghamshire",
    "kent": "Kent",
    "sussex": "Sussex",
    "hampshire": "Hampshire",
    "devon": "Devon",
    "cornwall": "Cornwall",
    "eastanglia": "East Anglia",
    "scotland": "Scotland",
    "wales": "Wales",
    "ni": "Northern Ireland",
}


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    url: str
    region: str
    topics: tuple[str, ...] = ()
    authority: float = 0.5
    locale: str | None = None
    aggregator: bool = False
    tags: tuple[str, ...] = field(default=())

    @property
    def is_local(self) -> bool:
        return self.region == "local"


def S(key, name, url, region, topics=(), authority=0.5, locale=None, aggregator=False):
    return Source(
        key=key,
        name=name,
        url=url,
        region=region,
        topics=tuple(topics),
        authority=authority,
        locale=locale,
        aggregator=aggregator,
    )


SOURCES: list[Source] = [
    # ------------------------------------------------------------------
    # UK national
    # ------------------------------------------------------------------
    S("bbc-top", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml", "uk", ["top"], 0.95),
    S("bbc-uk", "BBC UK", "https://feeds.bbci.co.uk/news/uk/rss.xml", "uk", ["top"], 0.95),
    S("bbc-politics", "BBC Politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "uk", ["politics"], 0.95),
    S("bbc-business", "BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "uk", ["business"], 0.93),
    S("bbc-tech", "BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "uk", ["tech"], 0.9),
    S("bbc-science", "BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "uk", ["science", "environment"], 0.9),
    S("bbc-health", "BBC Health", "https://feeds.bbci.co.uk/news/health/rss.xml", "uk", ["health"], 0.9),
    S("bbc-education", "BBC Education", "https://feeds.bbci.co.uk/news/education/rss.xml", "uk", ["top"], 0.88),
    S("bbc-ents", "BBC Culture", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "uk", ["culture"], 0.85),
    S("bbc-sport", "BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml", "uk", ["sport"], 0.9),
    S("bbc-world", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "world", ["top"], 0.95),

    S("guardian-uk", "The Guardian", "https://www.theguardian.com/uk/rss", "uk", ["top"], 0.9),
    S("guardian-politics", "Guardian Politics", "https://www.theguardian.com/politics/rss", "uk", ["politics"], 0.9),
    S("guardian-business", "Guardian Business", "https://www.theguardian.com/uk/business/rss", "uk", ["business"], 0.88),
    S("guardian-tech", "Guardian Tech", "https://www.theguardian.com/uk/technology/rss", "uk", ["tech"], 0.86),
    S("guardian-science", "Guardian Science", "https://www.theguardian.com/science/rss", "uk", ["science"], 0.86),
    S("guardian-env", "Guardian Environment", "https://www.theguardian.com/uk/environment/rss", "uk", ["environment"], 0.86),
    S("guardian-world", "Guardian World", "https://www.theguardian.com/world/rss", "world", ["top"], 0.9),
    S("guardian-football", "Guardian Football", "https://www.theguardian.com/football/rss", "uk", ["sport"], 0.85),
    S("guardian-culture", "Guardian Culture", "https://www.theguardian.com/uk/culture/rss", "uk", ["culture"], 0.82),

    S("sky-home", "Sky News", "https://feeds.skynews.com/feeds/rss/home.xml", "uk", ["top"], 0.85),
    S("sky-uk", "Sky News UK", "https://feeds.skynews.com/feeds/rss/uk.xml", "uk", ["top"], 0.85),
    S("sky-politics", "Sky Politics", "https://feeds.skynews.com/feeds/rss/politics.xml", "uk", ["politics"], 0.85),
    S("sky-business", "Sky Business", "https://feeds.skynews.com/feeds/rss/business.xml", "uk", ["business"], 0.83),
    S("sky-tech", "Sky Tech", "https://feeds.skynews.com/feeds/rss/technology.xml", "uk", ["tech"], 0.8),
    S("sky-world", "Sky World", "https://feeds.skynews.com/feeds/rss/world.xml", "world", ["top"], 0.85),

    S("telegraph-news", "The Telegraph", "https://www.telegraph.co.uk/news/rss.xml", "uk", ["top"], 0.8),
    S("telegraph-politics", "Telegraph Politics", "https://www.telegraph.co.uk/politics/rss.xml", "uk", ["politics"], 0.8),
    S("telegraph-business", "Telegraph Business", "https://www.telegraph.co.uk/business/rss.xml", "uk", ["business"], 0.78),

    S("independent-uk", "The Independent", "https://www.independent.co.uk/news/uk/rss", "uk", ["top"], 0.78),
    S("independent-politics", "Independent Politics", "https://www.independent.co.uk/news/uk/politics/rss", "uk", ["politics"], 0.78),
    S("independent-business", "Independent Business", "https://www.independent.co.uk/news/business/rss", "uk", ["business"], 0.75),
    S("independent-tech", "Independent Tech", "https://www.independent.co.uk/tech/rss", "uk", ["tech"], 0.74),
    S("independent-world", "Independent World", "https://www.independent.co.uk/news/world/rss", "world", ["top"], 0.76),

    S("standard-news", "Evening Standard", "https://www.standard.co.uk/news/rss", "uk", ["top"], 0.72),
    S("mirror-news", "The Mirror", "https://www.mirror.co.uk/news/?service=rss", "uk", ["top"], 0.55),
    S("express-news", "Daily Express", "https://feeds.feedburner.com/daily-express-news-showbiz", "uk", ["top"], 0.5),
    S("mail-news", "Daily Mail", "https://www.dailymail.co.uk/news/index.rss", "uk", ["top"], 0.5),
    S("metro-news", "Metro", "https://metro.co.uk/news/feed/", "uk", ["top"], 0.58),
    S("inews-uk", "The i Paper", "https://inews.co.uk/feed", "uk", ["top"], 0.74),
    S("bigissue", "The Big Issue", "https://www.bigissue.com/feed/", "uk", ["top"], 0.6),
    S("conversation-uk", "The Conversation UK", "https://theconversation.com/uk/articles.atom", "uk", ["science"], 0.75),
    S("openaccessgov", "Open Access Government", "https://www.openaccessgovernment.org/feed/", "uk", ["politics"], 0.5),

    S("cityam", "City A.M.", "https://www.cityam.com/feed/", "uk", ["business"], 0.7),
    S("thisismoney", "This is Money", "https://www.thisismoney.co.uk/money/index.rss", "uk", ["business"], 0.62),
    S("ft-home", "Financial Times", "https://www.ft.com/rss/home", "uk", ["business"], 0.92),
    S("ft-world", "FT World", "https://www.ft.com/world?format=rss", "world", ["business"], 0.9),
    S("economist", "The Economist", "https://www.economist.com/latest/rss.xml", "world", ["business", "politics"], 0.88),

    S("skysports", "Sky Sports", "https://www.skysports.com/rss/12040", "uk", ["sport"], 0.78),
    S("talksport", "talkSPORT", "https://talksport.com/feed/", "uk", ["sport"], 0.6),

    # ------------------------------------------------------------------
    # UK local / nations
    # ------------------------------------------------------------------
    S("bbc-london", "BBC London", "https://feeds.bbci.co.uk/news/england/london/rss.xml", "local", ["top"], 0.9, locale="london"),
    S("bbc-manchester", "BBC Manchester", "https://feeds.bbci.co.uk/news/england/manchester/rss.xml", "local", ["top"], 0.9, locale="manchester"),
    S("bbc-merseyside", "BBC Merseyside", "https://feeds.bbci.co.uk/news/england/merseyside/rss.xml", "local", ["top"], 0.9, locale="liverpool"),
    S("bbc-birmingham", "BBC Birmingham", "https://feeds.bbci.co.uk/news/england/birmingham_and_black_country/rss.xml", "local", ["top"], 0.9, locale="birmingham"),
    S("bbc-leeds", "BBC Leeds", "https://feeds.bbci.co.uk/news/england/leeds_and_west_yorkshire/rss.xml", "local", ["top"], 0.9, locale="leeds"),
    S("bbc-sheffield", "BBC Sheffield", "https://feeds.bbci.co.uk/news/england/south_yorkshire/rss.xml", "local", ["top"], 0.9, locale="sheffield"),
    S("bbc-tyne", "BBC Tyne", "https://feeds.bbci.co.uk/news/england/tyne_and_wear/rss.xml", "local", ["top"], 0.9, locale="newcastle"),
    S("bbc-bristol", "BBC Bristol", "https://feeds.bbci.co.uk/news/england/bristol/rss.xml", "local", ["top"], 0.9, locale="bristol"),
    S("bbc-nottingham", "BBC Nottingham", "https://feeds.bbci.co.uk/news/england/nottingham/rss.xml", "local", ["top"], 0.9, locale="nottingham"),
    S("bbc-kent", "BBC Kent", "https://feeds.bbci.co.uk/news/england/kent/rss.xml", "local", ["top"], 0.9, locale="kent"),
    S("bbc-sussex", "BBC Sussex", "https://feeds.bbci.co.uk/news/england/sussex/rss.xml", "local", ["top"], 0.9, locale="sussex"),
    S("bbc-hampshire", "BBC Hampshire", "https://feeds.bbci.co.uk/news/england/hampshire/rss.xml", "local", ["top"], 0.9, locale="hampshire"),
    S("bbc-devon", "BBC Devon", "https://feeds.bbci.co.uk/news/england/devon/rss.xml", "local", ["top"], 0.9, locale="devon"),
    S("bbc-cornwall", "BBC Cornwall", "https://feeds.bbci.co.uk/news/england/cornwall/rss.xml", "local", ["top"], 0.9, locale="cornwall"),
    S("bbc-norfolk", "BBC Norfolk", "https://feeds.bbci.co.uk/news/england/norfolk/rss.xml", "local", ["top"], 0.9, locale="eastanglia"),
    S("bbc-scotland", "BBC Scotland", "https://feeds.bbci.co.uk/news/scotland/rss.xml", "local", ["top"], 0.92, locale="scotland"),
    S("bbc-wales", "BBC Wales", "https://feeds.bbci.co.uk/news/wales/rss.xml", "local", ["top"], 0.92, locale="wales"),
    S("bbc-ni", "BBC Northern Ireland", "https://feeds.bbci.co.uk/news/northern_ireland/rss.xml", "local", ["top"], 0.92, locale="ni"),

    S("mylondon", "MyLondon", "https://www.mylondon.news/news/?service=rss", "local", ["top"], 0.55, locale="london"),
    S("men", "Manchester Evening News", "https://www.manchestereveningnews.co.uk/news/?service=rss", "local", ["top"], 0.62, locale="manchester"),
    S("liverpoolecho", "Liverpool Echo", "https://www.liverpoolecho.co.uk/news/?service=rss", "local", ["top"], 0.6, locale="liverpool"),
    S("birminghamlive", "Birmingham Live", "https://www.birminghammail.co.uk/news/?service=rss", "local", ["top"], 0.58, locale="birmingham"),
    S("leedslive", "Leeds Live", "https://www.leeds-live.co.uk/news/?service=rss", "local", ["top"], 0.55, locale="leeds"),
    S("yorkshirepost", "Yorkshire Post", "https://www.yorkshirepost.co.uk/rss", "local", ["top"], 0.62, locale="leeds"),
    S("sheffieldstar", "The Star Sheffield", "https://www.thestar.co.uk/rss", "local", ["top"], 0.58, locale="sheffield"),
    S("chroniclelive", "Chronicle Live", "https://www.chroniclelive.co.uk/news/?service=rss", "local", ["top"], 0.58, locale="newcastle"),
    S("bristolpost", "Bristol Live", "https://www.bristolpost.co.uk/news/?service=rss", "local", ["top"], 0.56, locale="bristol"),
    S("nottinghampost", "Nottinghamshire Live", "https://www.nottinghampost.com/news/?service=rss", "local", ["top"], 0.55, locale="nottingham"),
    S("theargus", "The Argus Brighton", "https://www.theargus.co.uk/news/rss/", "local", ["top"], 0.56, locale="sussex"),
    S("dailyecho", "Southern Daily Echo", "https://www.dailyecho.co.uk/news/rss/", "local", ["top"], 0.56, locale="hampshire"),
    S("devonlive", "Devon Live", "https://www.devonlive.com/news/?service=rss", "local", ["top"], 0.55, locale="devon"),
    S("cornwalllive", "Cornwall Live", "https://www.cornwalllive.com/news/?service=rss", "local", ["top"], 0.55, locale="cornwall"),
    S("edp24", "Eastern Daily Press", "https://www.edp24.co.uk/news/rss/", "local", ["top"], 0.56, locale="eastanglia"),
    S("cambridgenews", "Cambridgeshire Live", "https://www.cambridge-news.co.uk/news/?service=rss", "local", ["top"], 0.55, locale="eastanglia"),
    S("thenational-scot", "The National", "https://www.thenational.scot/news/rss", "local", ["top"], 0.6, locale="scotland"),
    S("heraldscotland", "The Herald", "https://www.heraldscotland.com/news/rss/", "local", ["top"], 0.66, locale="scotland"),
    S("scotsman", "The Scotsman", "https://www.scotsman.com/rss", "local", ["top"], 0.66, locale="scotland"),
    S("edinburghlive", "Edinburgh Live", "https://www.edinburghlive.co.uk/news/?service=rss", "local", ["top"], 0.54, locale="scotland"),
    S("glasgowlive", "Glasgow Live", "https://www.glasgowlive.co.uk/news/?service=rss", "local", ["top"], 0.54, locale="scotland"),
    S("pressandjournal", "Press and Journal", "https://www.pressandjournal.co.uk/feed/", "local", ["top"], 0.62, locale="scotland"),
    S("walesonline", "WalesOnline", "https://www.walesonline.co.uk/news/?service=rss", "local", ["top"], 0.6, locale="wales"),
    S("nation-cymru", "Nation.Cymru", "https://nation.cymru/feed/", "local", ["top"], 0.58, locale="wales"),
    S("belfasttelegraph", "Belfast Telegraph", "https://www.belfasttelegraph.co.uk/rss/", "local", ["top"], 0.66, locale="ni"),
    S("newsletter-ni", "News Letter", "https://www.newsletter.co.uk/rss", "local", ["top"], 0.6, locale="ni"),

    # ------------------------------------------------------------------
    # Ireland
    # ------------------------------------------------------------------
    S("rte-news", "RTÉ News", "https://www.rte.ie/feeds/rss/?index=/news/", "ie", ["top"], 0.85),
    S("irishtimes", "The Irish Times", "https://www.irishtimes.com/arc/outboundfeeds/feed-irish-news/", "ie", ["top"], 0.82),
    S("thejournal-ie", "TheJournal.ie", "https://www.thejournal.ie/feed/", "ie", ["top"], 0.7),
    S("independent-ie", "Irish Independent", "https://www.independent.ie/rss/", "ie", ["top"], 0.7),

    # ------------------------------------------------------------------
    # Europe
    # ------------------------------------------------------------------
    S("euronews", "Euronews", "https://www.euronews.com/rss?level=theme&name=news", "eu", ["top"], 0.78),
    S("euronews-europe", "Euronews Europe", "https://www.euronews.com/rss?level=vertical&name=my-europe", "eu", ["politics"], 0.78),
    S("politico-eu", "POLITICO Europe", "https://www.politico.eu/feed/", "eu", ["politics"], 0.82),
    S("euobserver", "EUobserver", "https://euobserver.com/rss", "eu", ["politics"], 0.76),
    S("dw-top", "Deutsche Welle", "https://rss.dw.com/rdf/rss-en-all", "eu", ["top"], 0.85),
    S("dw-europe", "DW Europe", "https://rss.dw.com/rdf/rss-en-eu", "eu", ["politics"], 0.85),
    S("france24", "France 24", "https://www.france24.com/en/rss", "eu", ["top"], 0.82),
    S("rfi-en", "RFI English", "https://www.rfi.fr/en/rss", "eu", ["top"], 0.78),
    S("spiegel-intl", "Der Spiegel", "https://www.spiegel.de/international/index.rss", "eu", ["top"], 0.82),
    S("elpais-en", "El País English", "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada", "eu", ["top"], 0.8),
    S("ansa-en", "ANSA English", "https://www.ansa.it/english/english_rss.xml", "eu", ["top"], 0.76),
    S("nltimes", "NL Times", "https://nltimes.nl/rss.xml", "eu", ["top"], 0.7),
    S("thelocal-de", "The Local Germany", "https://www.thelocal.de/feeds/rss.php", "eu", ["top"], 0.62),
    S("thelocal-fr", "The Local France", "https://www.thelocal.fr/feeds/rss.php", "eu", ["top"], 0.62),
    S("kyivpost", "Kyiv Post", "https://www.kyivpost.com/feed", "eu", ["security"], 0.7),
    S("balkaninsight", "Balkan Insight", "https://balkaninsight.com/feed/", "eu", ["politics"], 0.72),
    S("notesfrompoland", "Notes from Poland", "https://notesfrompoland.com/feed/", "eu", ["politics"], 0.68),
    S("emerging-europe", "Emerging Europe", "https://emerging-europe.com/feed/", "eu", ["business"], 0.6),

    # ------------------------------------------------------------------
    # United States
    # ------------------------------------------------------------------
    S("nyt-home", "The New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "us", ["top"], 0.92),
    S("nyt-us", "NYT US", "https://rss.nytimes.com/services/xml/rss/nyt/US.xml", "us", ["top"], 0.92),
    S("nyt-politics", "NYT Politics", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "us", ["politics"], 0.92),
    S("nyt-business", "NYT Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "us", ["business"], 0.9),
    S("nyt-tech", "NYT Tech", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "us", ["tech"], 0.9),
    S("nyt-science", "NYT Science", "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", "us", ["science"], 0.9),
    S("nyt-health", "NYT Health", "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml", "us", ["health"], 0.9),
    S("nyt-world", "NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "world", ["top"], 0.92),
    S("wapo-politics", "Washington Post Politics", "https://feeds.washingtonpost.com/rss/politics", "us", ["politics"], 0.88),
    S("wapo-world", "Washington Post World", "https://feeds.washingtonpost.com/rss/world", "world", ["top"], 0.88),
    S("wapo-business", "Washington Post Business", "https://feeds.washingtonpost.com/rss/business", "us", ["business"], 0.86),
    S("npr-news", "NPR", "https://feeds.npr.org/1001/rss.xml", "us", ["top"], 0.88),
    S("npr-politics", "NPR Politics", "https://feeds.npr.org/1014/rss.xml", "us", ["politics"], 0.88),
    S("npr-world", "NPR World", "https://feeds.npr.org/1004/rss.xml", "world", ["top"], 0.88),
    S("npr-business", "NPR Business", "https://feeds.npr.org/1006/rss.xml", "us", ["business"], 0.85),
    S("npr-science", "NPR Science", "https://feeds.npr.org/1007/rss.xml", "us", ["science"], 0.85),
    S("cnn-top", "CNN", "http://rss.cnn.com/rss/cnn_topstories.rss", "us", ["top"], 0.78),
    S("cnn-us", "CNN US", "http://rss.cnn.com/rss/cnn_us.rss", "us", ["top"], 0.78),
    S("cnn-world", "CNN World", "http://rss.cnn.com/rss/cnn_world.rss", "world", ["top"], 0.78),
    S("cbs-main", "CBS News", "https://www.cbsnews.com/latest/rss/main", "us", ["top"], 0.8),
    S("cbs-politics", "CBS Politics", "https://www.cbsnews.com/latest/rss/politics", "us", ["politics"], 0.8),
    S("cbs-world", "CBS World", "https://www.cbsnews.com/latest/rss/world", "world", ["top"], 0.8),
    S("abc-top", "ABC News", "https://feeds.abcnews.com/abcnews/topstories", "us", ["top"], 0.8),
    S("abc-politics", "ABC Politics", "https://feeds.abcnews.com/abcnews/politicsheadlines", "us", ["politics"], 0.8),
    S("nbc-top", "NBC News", "https://feeds.nbcnews.com/nbcnews/public/news", "us", ["top"], 0.8),
    S("nbc-politics", "NBC Politics", "https://feeds.nbcnews.com/nbcnews/public/politics", "us", ["politics"], 0.8),
    S("fox-latest", "Fox News", "https://moxie.foxnews.com/google-publisher/latest.xml", "us", ["top"], 0.68),
    S("fox-politics", "Fox Politics", "https://moxie.foxnews.com/google-publisher/politics.xml", "us", ["politics"], 0.68),
    S("politico-us", "POLITICO", "https://rss.politico.com/politics-news.xml", "us", ["politics"], 0.82),
    S("thehill", "The Hill", "https://thehill.com/news/feed/", "us", ["politics"], 0.74),
    S("axios", "Axios", "https://api.axios.com/feed/", "us", ["top"], 0.78),
    S("latimes", "Los Angeles Times", "https://www.latimes.com/rss2.0.xml", "us", ["top"], 0.8),
    S("propublica", "ProPublica", "https://www.propublica.org/feeds/propublica/main", "us", ["politics"], 0.84),
    S("theatlantic", "The Atlantic", "https://www.theatlantic.com/feed/all/", "us", ["culture"], 0.78),
    S("vox", "Vox", "https://www.vox.com/rss/index.xml", "us", ["politics"], 0.7),
    S("cnbc-top", "CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "us", ["business"], 0.82),
    S("cnbc-econ", "CNBC Economy", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "us", ["business"], 0.8),
    S("marketwatch", "MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "us", ["business"], 0.78),
    S("fortune", "Fortune", "https://fortune.com/feed/fortune-feeds/?id=3230629", "us", ["business"], 0.7),
    S("businessinsider", "Business Insider", "https://feeds.businessinsider.com/custom/all", "us", ["business"], 0.65),
    S("statnews", "STAT", "https://www.statnews.com/feed/", "us", ["health"], 0.8),

    # ------------------------------------------------------------------
    # World
    # ------------------------------------------------------------------
    S("aljazeera", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "world", ["top"], 0.84),
    S("un-news", "UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "world", ["top"], 0.8),
    S("reliefweb", "ReliefWeb", "https://reliefweb.int/updates/rss.xml", "world", ["security"], 0.72),
    S("cbc-world", "CBC News", "https://www.cbc.ca/webfeed/rss/rss-world", "world", ["top"], 0.82),
    S("cbc-top", "CBC Top Stories", "https://www.cbc.ca/webfeed/rss/rss-topstories", "world", ["top"], 0.82),
    S("globeandmail", "The Globe and Mail", "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/world/", "world", ["top"], 0.78),
    S("abc-au", "ABC Australia", "https://www.abc.net.au/news/feed/51120/rss.xml", "world", ["top"], 0.84),
    S("smh", "Sydney Morning Herald", "https://www.smh.com.au/rss/world.xml", "world", ["top"], 0.76),
    S("nzherald", "NZ Herald", "https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/world/?outputType=xml", "world", ["top"], 0.7),
    S("scmp", "South China Morning Post", "https://www.scmp.com/rss/91/feed", "world", ["top"], 0.78),
    S("japantimes", "The Japan Times", "https://www.japantimes.co.jp/feed/", "world", ["top"], 0.76),
    S("straitstimes", "The Straits Times", "https://www.straitstimes.com/news/world/rss.xml", "world", ["top"], 0.74),
    S("thehindu", "The Hindu", "https://www.thehindu.com/news/international/feeder/default.rss", "world", ["top"], 0.74),
    S("toi-world", "Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", "world", ["top"], 0.66),
    S("dawn", "Dawn", "https://www.dawn.com/feeds/home", "world", ["top"], 0.7),
    S("timesofisrael", "The Times of Israel", "https://www.timesofisrael.com/feed/", "world", ["security"], 0.72),
    S("arabnews", "Arab News", "https://www.arabnews.com/rss.xml", "world", ["top"], 0.68),
    S("middleeasteye", "Middle East Eye", "https://www.middleeasteye.net/rss", "world", ["security"], 0.68),
    S("africanews", "Africanews", "https://www.africanews.com/feed/rss", "world", ["top"], 0.7),
    S("allafrica", "AllAfrica", "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "world", ["top"], 0.68),
    S("mg-za", "Mail & Guardian", "https://mg.co.za/rss/", "world", ["top"], 0.7),
    S("batimes", "Buenos Aires Times", "https://www.batimes.com.ar/feed", "world", ["top"], 0.64),
    S("riotimes", "The Rio Times", "https://www.riotimesonline.com/feed/", "world", ["top"], 0.6),

    # ------------------------------------------------------------------
    # Technology
    # ------------------------------------------------------------------
    S("verge", "The Verge", "https://www.theverge.com/rss/index.xml", "us", ["tech"], 0.8),
    S("arstechnica", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "us", ["tech"], 0.82),
    S("techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "us", ["tech"], 0.75),
    S("wired", "WIRED", "https://www.wired.com/feed/rss", "us", ["tech"], 0.78),
    S("engadget", "Engadget", "https://www.engadget.com/rss.xml", "us", ["tech"], 0.7),
    S("theregister", "The Register", "https://www.theregister.com/headlines.atom", "uk", ["tech"], 0.76),
    S("hackernews", "Hacker News", "https://hnrss.org/frontpage", "world", ["tech"], 0.7),
    S("bleepingcomputer", "BleepingComputer", "https://www.bleepingcomputer.com/feed/", "world", ["security", "tech"], 0.78),
    S("krebs", "Krebs on Security", "https://krebsonsecurity.com/feed/", "us", ["security"], 0.82),
    S("therecord", "The Record", "https://therecord.media/feed", "world", ["security"], 0.78),
    S("techmeme", "Techmeme", "https://www.techmeme.com/feed.xml", "us", ["tech"], 0.72),
    S("mit-techreview", "MIT Technology Review", "https://www.technologyreview.com/feed/", "us", ["tech"], 0.8),
    S("ieee-spectrum", "IEEE Spectrum", "https://spectrum.ieee.org/feeds/feed.rss", "us", ["tech"], 0.78),
    S("zdnet", "ZDNET", "https://www.zdnet.com/news/rss.xml", "us", ["tech"], 0.66),
    S("9to5mac", "9to5Mac", "https://9to5mac.com/feed/", "us", ["tech"], 0.62),
    S("androidpolice", "Android Police", "https://www.androidpolice.com/feed/", "us", ["tech"], 0.6),

    # ------------------------------------------------------------------
    # Science / health / environment
    # ------------------------------------------------------------------
    S("nature", "Nature", "https://www.nature.com/nature.rss", "world", ["science"], 0.9),
    S("science-mag", "Science", "https://www.science.org/rss/news_current.xml", "world", ["science"], 0.9),
    S("newscientist", "New Scientist", "https://www.newscientist.com/feed/home/", "uk", ["science"], 0.8),
    S("physorg", "Phys.org", "https://phys.org/rss-feed/", "world", ["science"], 0.72),
    S("sciam", "Scientific American", "https://www.scientificamerican.com/platform/syndication/rss/", "us", ["science"], 0.8),
    S("space-com", "Space.com", "https://www.space.com/feeds/all", "us", ["science"], 0.68),
    S("nasa", "NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss", "us", ["science"], 0.85),
    S("esa", "ESA", "https://www.esa.int/rssfeed/Our_Activities/Space_News", "eu", ["science"], 0.82),
    S("who-news", "WHO", "https://www.who.int/rss-feeds/news-english.xml", "world", ["health"], 0.85),
    S("carbonbrief", "Carbon Brief", "https://www.carbonbrief.org/feed/", "uk", ["environment"], 0.8),
    S("yaleclimate", "Yale Climate Connections", "https://yaleclimateconnections.org/feed/", "us", ["environment"], 0.72),

    # ------------------------------------------------------------------
    # Ukraine / Russia - high news volume, worth its own cluster of sources
    # ------------------------------------------------------------------
    S("ukrinform", "Ukrinform", "https://www.ukrinform.net/rss/block-lastnews", "eu", ["security"], 0.72),
    S("pravda-en", "Ukrainska Pravda", "https://www.pravda.com.ua/eng/rss/", "eu", ["security"], 0.74),
    S("moscowtimes", "The Moscow Times", "https://www.themoscowtimes.com/rss/news", "eu", ["security"], 0.74),

    # ------------------------------------------------------------------
    # Europe - wider national coverage
    # ------------------------------------------------------------------
    S("vrtnws", "VRT NWS", "https://www.vrt.be/vrtnws/en.rss.articles.xml", "eu", ["top"], 0.76),
    S("lemonde-en", "Le Monde English", "https://www.lemonde.fr/en/rss/une.xml", "eu", ["top"], 0.84),
    S("faz", "FAZ", "https://www.faz.net/rss/aktuell/", "eu", ["top"], 0.8),
    S("dutchnews", "DutchNews.nl", "https://www.dutchnews.nl/feed/", "eu", ["top"], 0.66),
    S("thelocal-it", "The Local Italy", "https://www.thelocal.it/feeds/rss.php", "eu", ["top"], 0.62),
    S("thelocal-es", "The Local Spain", "https://www.thelocal.es/feeds/rss.php", "eu", ["top"], 0.62),
    S("cyprusmail", "Cyprus Mail", "https://cyprus-mail.com/feed/", "eu", ["top"], 0.62),
    S("portugalnews", "The Portugal News", "https://www.theportugalnews.com/rss", "eu", ["top"], 0.6),
    S("intellinews", "bne IntelliNews", "https://www.intellinews.com/feed", "eu", ["business"], 0.68),
    S("aa-en", "Anadolu Agency", "https://www.aa.com.tr/en/rss/default?cat=live", "eu", ["top"], 0.66),

    # ------------------------------------------------------------------
    # UK - additional perspectives
    # ------------------------------------------------------------------
    S("gbnews", "GB News", "https://www.gbnews.com/feeds/news.rss", "uk", ["top"], 0.5),
    S("unherd", "UnHerd", "https://unherd.com/feed/", "uk", ["politics"], 0.62),
    S("bylinetimes", "Byline Times", "https://bylinetimes.com/feed/", "uk", ["politics"], 0.6),
    S("opendemocracy", "openDemocracy", "https://www.opendemocracy.net/en/feed/", "uk", ["politics"], 0.64),
    S("energylivenews", "Energy Live News", "https://www.energylivenews.com/feed/", "uk", ["environment", "business"], 0.55),
    S("constructionnews", "Construction News", "https://www.constructionnews.co.uk/feed/", "uk", ["business"], 0.55),

    # ------------------------------------------------------------------
    # US / Americas - additional
    # ------------------------------------------------------------------
    S("guardian-us", "Guardian US", "https://www.theguardian.com/us-news/rss", "us", ["top"], 0.86),
    S("csmonitor", "Christian Science Monitor", "https://rss.csmonitor.com/feeds/usa", "us", ["top"], 0.78),
    S("semafor", "Semafor", "https://www.semafor.com/rss.xml", "us", ["top"], 0.72),
    S("mercopress", "MercoPress", "https://en.mercopress.com/rss/", "world", ["top"], 0.62),
    S("grist", "Grist", "https://grist.org/feed/", "us", ["environment"], 0.72),

    # ------------------------------------------------------------------
    # Asia / Africa / Middle East - additional
    # ------------------------------------------------------------------
    S("nikkei-asia", "Nikkei Asia", "https://asia.nikkei.com/rss/feed/nar", "world", ["business"], 0.8),
    S("cna", "CNA", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml", "world", ["top"], 0.76),
    S("koreaherald", "The Korea Herald", "https://www.koreaherald.com/rss/newsAll", "world", ["top"], 0.68),
    S("bangkokpost", "Bangkok Post", "https://www.bangkokpost.com/rss/data/topstories.xml", "world", ["top"], 0.68),
    S("jpost", "The Jerusalem Post", "https://www.jpost.com/rss/rssfeedsfrontpage.aspx", "world", ["security"], 0.7),
    S("dailymaverick", "Daily Maverick", "https://www.dailymaverick.co.za/dmrss/", "world", ["top"], 0.72),
    S("premiumtimes", "Premium Times", "https://www.premiumtimesng.com/feed", "world", ["top"], 0.68),

    # ------------------------------------------------------------------
    # Aggregators - broad safety net, discounted in scoring
    # ------------------------------------------------------------------
    S("gnews-uk", "Google News UK", "https://news.google.com/rss?hl=en-GB&gl=GB&ceid=GB:en", "uk", ["top"], 0.45, aggregator=True),
    S("gnews-world", "Google News World", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-GB&gl=GB&ceid=GB:en", "world", ["top"], 0.45, aggregator=True),
    S("gnews-business", "Google News Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-GB&gl=GB&ceid=GB:en", "uk", ["business"], 0.42, aggregator=True),
    S("gnews-tech", "Google News Tech", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-GB&gl=GB&ceid=GB:en", "uk", ["tech"], 0.42, aggregator=True),
    S("gnews-us", "Google News US", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en", "us", ["top"], 0.45, aggregator=True),
]


SOURCES_BY_KEY = {s.key: s for s in SOURCES}


def sources_for(region: str | None = None, topic: str | None = None, locale: str | None = None):
    out = []
    for s in SOURCES:
        if region and s.region != region:
            continue
        if topic and topic not in s.topics:
            continue
        if locale and s.locale and s.locale != locale:
            continue
        out.append(s)
    return out
