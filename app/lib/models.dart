import 'package:intl/intl.dart';

class Story {
  Story({
    required this.id,
    required this.title,
    required this.url,
    required this.source,
    required this.altTitle,
    required this.region,
    required this.regions,
    required this.topics,
    required this.locales,
    required this.published,
    required this.sources,
    required this.impact,
    required this.coverage,
  });

  final int id;
  final String title;
  final String url;
  final String source;

  /// A second outlet's framing of the same story. Shown under the lead as a
  /// standfirst - it gives the reader a second angle without a second tap.
  final String altTitle;

  final String region;
  final List<String> regions;
  final List<String> topics;
  final List<String> locales;
  final DateTime published;

  /// Distinct newsrooms carrying this story. The human-readable form of the
  /// impact score, and the number readers actually trust.
  final int sources;

  final double impact;
  final List<Coverage> coverage;

  factory Story.fromJson(Map<String, dynamic> j) => Story(
        id: j['id'] as int,
        title: (j['title'] ?? '') as String,
        url: (j['url'] ?? '') as String,
        source: (j['source'] ?? '') as String,
        altTitle: (j['alt_title'] ?? '') as String,
        region: (j['region'] ?? 'world') as String,
        regions: List<String>.from(j['regions'] ?? const []),
        topics: List<String>.from(j['topics'] ?? const []),
        locales: List<String>.from(j['locales'] ?? const []),
        published: DateTime.tryParse((j['published'] ?? '') as String)?.toLocal() ??
            DateTime.now(),
        sources: (j['sources'] ?? 1) as int,
        impact: ((j['impact'] ?? 0) as num).toDouble(),
        coverage: ((j['coverage'] ?? const []) as List)
            .map((e) => Coverage.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  /// Compact relative time, the way a wire desk writes it: 4m, 2h, then the
  /// clock time for anything from an earlier day.
  String get age {
    final d = DateTime.now().difference(published);
    if (d.inMinutes < 1) return 'now';
    if (d.inMinutes < 60) return '${d.inMinutes}m';
    if (d.inHours < 24) return '${d.inHours}h';
    if (d.inDays == 1) return 'Yesterday';
    return DateFormat('d MMM').format(published);
  }

  bool get isFresh => DateTime.now().difference(published).inMinutes < 45;
}

class Coverage {
  Coverage({
    required this.source,
    required this.title,
    required this.url,
    required this.published,
  });

  final String source;
  final String title;
  final String url;
  final DateTime published;

  factory Coverage.fromJson(Map<String, dynamic> j) => Coverage(
        source: (j['source'] ?? '') as String,
        title: (j['title'] ?? '') as String,
        url: (j['url'] ?? '') as String,
        published: DateTime.tryParse((j['published'] ?? '') as String)?.toLocal() ??
            DateTime.now(),
      );

  String get age {
    final d = DateTime.now().difference(published);
    if (d.inMinutes < 60) return '${d.inMinutes}m';
    if (d.inHours < 24) return '${d.inHours}h';
    return DateFormat('d MMM').format(published);
  }
}

class Section {
  const Section(this.key, this.label);
  final String key;
  final String label;

  factory Section.fromJson(Map<String, dynamic> j) =>
      Section((j['key'] ?? '') as String, (j['label'] ?? '') as String);
}

class AppConfig {
  const AppConfig({
    required this.regions,
    required this.topics,
    required this.locales,
    required this.sourceCount,
    required this.defaultWeights,
  });

  final List<Section> regions;
  final List<Section> topics;
  final List<Section> locales;
  final int sourceCount;
  final Map<String, double> defaultWeights;

  factory AppConfig.fromJson(Map<String, dynamic> j) => AppConfig(
        regions: ((j['regions'] ?? const []) as List)
            .map((e) => Section.fromJson(e as Map<String, dynamic>))
            .toList(),
        topics: ((j['topics'] ?? const []) as List)
            .map((e) => Section.fromJson(e as Map<String, dynamic>))
            .toList(),
        locales: ((j['locales'] ?? const []) as List)
            .map((e) => Section.fromJson(e as Map<String, dynamic>))
            .toList(),
        sourceCount: (j['source_count'] ?? 0) as int,
        defaultWeights: ((j['default_weights'] ?? const {}) as Map)
            .map((k, v) => MapEntry(k as String, (v as num).toDouble())),
      );

  static const fallback = AppConfig(
    regions: [
      Section('local', 'Local'),
      Section('uk', 'UK'),
      Section('ie', 'Ireland'),
      Section('eu', 'Europe'),
      Section('us', 'US'),
      Section('world', 'World'),
    ],
    topics: [
      Section('top', 'Top'),
      Section('politics', 'Politics'),
      Section('business', 'Business'),
      Section('tech', 'Tech'),
      Section('science', 'Science'),
      Section('health', 'Health'),
      Section('environment', 'Climate'),
      Section('sport', 'Sport'),
      Section('culture', 'Culture'),
      Section('security', 'Security'),
    ],
    locales: [],
    sourceCount: 0,
    defaultWeights: {
      'local': 1.5,
      'uk': 3.0,
      'ie': 0.5,
      'eu': 1.5,
      'us': 1.5,
      'world': 2.0,
    },
  );
}

class HeadlineFeed {
  const HeadlineFeed({required this.stories, required this.generatedAt});
  final List<Story> stories;
  final DateTime generatedAt;

  factory HeadlineFeed.fromJson(Map<String, dynamic> j) => HeadlineFeed(
        stories: ((j['stories'] ?? const []) as List)
            .map((e) => Story.fromJson(e as Map<String, dynamic>))
            .toList(),
        generatedAt:
            DateTime.tryParse((j['generated_at'] ?? '') as String)?.toLocal() ??
                DateTime.now(),
      );
}
