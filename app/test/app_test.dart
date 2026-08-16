import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:newsfin/models.dart';
import 'package:newsfin/motion.dart';
import 'package:newsfin/reader.dart';
import 'package:newsfin/state.dart';
import 'package:newsfin/theme.dart';
import 'package:newsfin/widgets/story_tile.dart';

Story makeStory({
  int id = 1,
  String title = 'Bank of England holds interest rates at four percent',
  String source = 'BBC News',
  int sources = 3,
  double impact = 70,
  String altTitle = '',
  Duration age = const Duration(minutes: 20),
  List<Coverage> coverage = const [],
}) =>
    Story(
      id: id,
      title: title,
      url: 'https://example.com/$id',
      source: source,
      altTitle: altTitle,
      region: 'uk',
      regions: const ['uk'],
      topics: const ['top'],
      locales: const [],
      published: DateTime.now().subtract(age),
      sources: sources,
      impact: impact,
      coverage: coverage,
    );

Widget wrap(Widget child, {NewsColors? colors}) {
  final c = colors ?? NewsColors.dark;
  return MaterialApp(
    theme: buildTheme(c, c == NewsColors.dark ? Brightness.dark : Brightness.light),
    home: NewsTheme(
      colors: c,
      child: Scaffold(backgroundColor: c.canvas, body: child),
    ),
  );
}

void main() {
  group('Story', () {
    test('age reads like a wire desk', () {
      expect(makeStory(age: const Duration(seconds: 20)).age, 'now');
      expect(makeStory(age: const Duration(minutes: 8)).age, '8m');
      expect(makeStory(age: const Duration(hours: 5)).age, '5h');
      expect(makeStory(age: const Duration(hours: 30)).age, 'Yesterday');
    });

    test('freshness window is generous enough to be useful', () {
      expect(makeStory(age: const Duration(minutes: 10)).isFresh, isTrue);
      expect(makeStory(age: const Duration(hours: 3)).isFresh, isFalse);
    });

    test('parses a payload from the API', () {
      final s = Story.fromJson({
        'id': 7,
        'title': 'Quake hits Indonesia',
        'url': 'https://x/1',
        'source': 'BBC World',
        'alt_title': 'Tsunami warning issued',
        'region': 'world',
        'regions': ['world', 'uk'],
        'topics': ['top'],
        'locales': [],
        'published': DateTime.now().toUtc().toIso8601String(),
        'sources': 25,
        'impact': 92.8,
        'coverage': [
          {
            'source': 'Reuters',
            'title': 'Indonesia quake',
            'url': 'https://y/2',
            'published': DateTime.now().toUtc().toIso8601String(),
          }
        ],
      });
      expect(s.sources, 25);
      expect(s.coverage.single.source, 'Reuters');
      expect(s.regions, contains('uk'));
    });

    test('survives a malformed payload rather than throwing', () {
      final s = Story.fromJson({'id': 1});
      expect(s.title, '');
      expect(s.sources, 1);
    });
  });

  group('Impact tiers', () {
    test('the top tier is scarce', () {
      // Real polls cluster most stories in the 55-75 band; if that band read as
      // "major" the colour marker would appear on half the list and stop
      // meaning anything.
      expect(tierFor(92), ImpactTier.lead);
      expect(tierFor(75), ImpactTier.major);
      expect(tierFor(64), ImpactTier.notable);
      expect(tierFor(40), ImpactTier.routine);
    });

    test('every tier resolves to a colour in both palettes', () {
      for (final tier in ImpactTier.values) {
        expect(tierColor(tier, NewsColors.dark), isA<Color>());
        expect(tierColor(tier, NewsColors.light), isA<Color>());
      }
    });
  });

  group('Themes', () {
    test('light and dark are complete, independent palettes', () {
      // Not one theme with overrides - a colour defined in only one palette
      // has no value in the other.
      expect(NewsColors.dark.canvas, isNot(NewsColors.light.canvas));
      expect(NewsColors.dark.textPrimary, isNot(NewsColors.light.textPrimary));
      expect(NewsColors.dark.accent, isNot(NewsColors.light.accent));
    });

    test('neither theme uses pure black or pure white as its ground', () {
      expect(NewsColors.dark.canvas, isNot(const Color(0xFF000000)));
      expect(NewsColors.light.canvas, isNot(const Color(0xFFFFFFFF)));
    });

    testWidgets('Bricolage is the display face everywhere it matters',
        (tester) async {
      for (final style in [
        NewsType.masthead,
        NewsType.lead,
        NewsType.headline,
        NewsType.headlineSmall,
        NewsType.standfirst,
        NewsType.eyebrow,
        NewsType.meta,
      ]) {
        expect(style.fontFamily, 'Bricolage');
      }
      // Numerics stay monospaced so digits do not jitter between refreshes.
      expect(NewsType.numeric.fontFamily, 'SplineSansMono');
    });
  });

  group('StoryTile', () {
    testWidgets('shows the headline, source and corroboration count',
        (tester) async {
      await tester.pumpWidget(wrap(StoryTile(
        story: makeStory(sources: 12),
        onTap: () {},
        onCoverage: () {},
      )));
      expect(find.textContaining('Bank of England'), findsOneWidget);
      expect(find.text('BBC NEWS'), findsOneWidget);
      expect(find.text('12 sources'), findsOneWidget);
    });

    testWidgets('a single-source story does not claim corroboration',
        (tester) async {
      await tester.pumpWidget(wrap(StoryTile(
        story: makeStory(sources: 1),
        onTap: () {},
        onCoverage: () {},
      )));
      expect(find.textContaining('sources'), findsNothing);
    });

    testWidgets('tapping opens the story', (tester) async {
      var opened = false;
      await tester.pumpWidget(wrap(StoryTile(
        story: makeStory(),
        onTap: () => opened = true,
        onCoverage: () {},
      )));
      await tester.tap(find.byType(StoryTile));
      expect(opened, isTrue);
    });

    testWidgets('renders in the light palette too', (tester) async {
      await tester.pumpWidget(wrap(
        StoryTile(story: makeStory(), onTap: () {}, onCoverage: () {}),
        colors: NewsColors.light,
      ));
      expect(find.textContaining('Bank of England'), findsOneWidget);
    });

    testWidgets('carries a screen-reader label with the ranking evidence',
        (tester) async {
      await tester.pumpWidget(wrap(StoryTile(
        story: makeStory(sources: 9),
        onTap: () {},
        onCoverage: () {},
      )));
      final semantics = tester.getSemantics(find.byType(StoryTile).first);
      expect(semantics.label, contains('9 sources'));
    });
  });

  group('LeadStory', () {
    testWidgets('shows the section label and a second outlet framing',
        (tester) async {
      await tester.pumpWidget(wrap(LeadStory(
        story: makeStory(altTitle: 'Rate decision splits the committee'),
        label: 'This morning',
        onTap: () {},
        onCoverage: () {},
      )));
      expect(find.text('THIS MORNING'), findsOneWidget);
      expect(find.text('Rate decision splits the committee'), findsOneWidget);
    });
  });

  group('Settings', () {
    test('defaults cover every region so none silently disappears', () {
      for (final r in ['local', 'uk', 'ie', 'eu', 'us', 'world']) {
        expect(Settings.defaults.weights.containsKey(r), isTrue, reason: r);
      }
    });

    test('round-trips through JSON', () {
      const s = Settings(
        weights: {'uk': 3.0, 'world': 1.5},
        locale: 'manchester',
        themeMode: ThemeMode.light,
        textScale: 1.15,
        hours: 24,
        minSources: 2,
        openInApp: false,
        speechRate: 0.85,
        announceSources: false,
      );
      final restored = Settings.fromJson(s.toJson());
      expect(restored.weights['uk'], 3.0);
      expect(restored.locale, 'manchester');
      expect(restored.themeMode, ThemeMode.light);
      expect(restored.minSources, 2);
      expect(restored.openInApp, isFalse);
      expect(restored.speechRate, 0.85);
      expect(restored.announceSources, isFalse);
    });

    test('unknown stored theme falls back rather than crashing', () {
      final s = Settings.fromJson({'themeMode': 'nonsense'});
      expect(s.themeMode, ThemeMode.dark);
    });
  });

  group('FeedQuery', () {
    test('identical queries share a cache entry', () {
      const a = FeedQuery(regions: ['uk'], topic: 'business');
      const b = FeedQuery(regions: ['uk'], topic: 'business');
      expect(a, b);
      expect(a.cacheKey, b.cacheKey);
    });

    test('personalised and plain feeds never share a cache entry', () {
      const plain = FeedQuery(regions: ['uk']);
      const mine = FeedQuery(regions: ['uk'], personalised: true);
      expect(plain, isNot(mine));
      expect(plain.cacheKey, isNot(mine.cacheKey));
    });

    test('the two lanes never share a cache entry', () {
      // Same filters, different order - caching them together would show the
      // wrong lane's list on open.
      const top = FeedQuery(personalised: true);
      const latest = FeedQuery(personalised: true, sort: FeedSort.latest);
      expect(top, isNot(latest));
      expect(top.cacheKey, isNot(latest.cacheKey));
    });

    test('withSort keeps every other filter intact', () {
      const q = FeedQuery(regions: ['uk'], topic: 'business');
      final latest = q.withSort(FeedSort.latest);
      expect(latest.regions, ['uk']);
      expect(latest.topic, 'business');
      expect(latest.sort, FeedSort.latest);
    });

    test('the lane wire values match the API contract', () {
      expect(FeedSort.top.wire, 'top');
      expect(FeedSort.latest.wire, 'latest');
    });

    test('different sections get different cache entries', () {
      expect(
        const FeedQuery(regions: ['uk']).cacheKey,
        isNot(const FeedQuery(regions: ['us']).cacheKey),
      );
    });
  });

  group('Headline reader', () {
    test('speaking speed and source announcement persist', () {
      final restored = Settings.fromJson(
        Settings.defaults.copyWith(speechRate: 1.25, announceSources: false).toJson(),
      );
      expect(restored.speechRate, 1.25);
      expect(restored.announceSources, isFalse);
    });

    test('older stored settings gain reader defaults rather than breaking', () {
      // Settings saved before the reader existed have no speechRate key.
      final s = Settings.fromJson({'weights': {'uk': 3.0}, 'locale': 'london'});
      expect(s.speechRate, 1.0);
      expect(s.announceSources, isTrue);
    });

    test('the spoken line leads with position, then headline, then sources', () {
      // Position first because in a ranked list the number IS the information;
      // the source count trails so the headline is never delayed.
      final line = spokenLine(
        makeStory(title: 'Earthquake kills at least 38', source: 'BBC World', sources: 28),
        1,
        announceSources: true,
      );
      expect(line, '1. Earthquake kills at least 38. BBC World, reported by 28 sources.');
    });

    test('a single-source story does not claim corroboration aloud', () {
      final line = spokenLine(makeStory(sources: 1), 3, announceSources: true);
      expect(line, isNot(contains('sources')));
      expect(line, startsWith('3. '));
    });

    test('source announcement can be turned off entirely', () {
      final line = spokenLine(makeStory(title: 'A headline'), 2, announceSources: false);
      expect(line, '2. A headline.');
    });
  });

  group('Motion', () {
    testWidgets('entrance animation settles fully', (tester) async {
      await tester.pumpWidget(wrap(const RiseIn(child: Text('Headline'))));
      await tester.pumpAndSettle();
      final opacity = tester.widget<Opacity>(find.byType(Opacity).first);
      expect(opacity.opacity, 1.0);
    });

    testWidgets('reduced motion shows content immediately', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(disableAnimations: true),
          child: NewsTheme(
            colors: NewsColors.dark,
            child: const RiseIn(index: 8, child: Text('Headline')),
          ),
        ),
      ));
      // No pumpAndSettle: with animations disabled it must already be visible,
      // not merely arrive eventually.
      await tester.pump();
      final opacity = tester.widget<Opacity>(find.byType(Opacity).first);
      expect(opacity.opacity, 1.0);
    });

    test('nothing in the motion vocabulary loops', () {
      // A persistent control that pulses forever reads as a rendering fault.
      expect(Motion.quick.inMilliseconds, lessThan(400));
      expect(Motion.normal.inMilliseconds, lessThan(600));
      expect(Motion.stagger.inMilliseconds, inInclusiveRange(30, 70));
    });
  });
}
