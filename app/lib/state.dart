import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'models.dart';

final apiProvider = Provider<NewsApi>((ref) => NewsApi());

final configProvider = FutureProvider<AppConfig>((ref) async {
  return ref.watch(apiProvider).config();
});

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

/// What the reader considers important. This is the whole point of the
/// Headlines tab: the same 200 feeds, ordered by what *this* reader cares
/// about, rather than one editor's idea of a front page.
class Settings {
  const Settings({
    required this.weights,
    required this.locale,
    required this.themeMode,
    required this.textScale,
    required this.hours,
    required this.minSources,
    required this.openInApp,
  });

  final Map<String, double> weights;
  final String locale;
  final ThemeMode themeMode;
  final double textScale;
  final int hours;

  /// Raise this to hide single-source chatter and see only stories that
  /// multiple newsrooms independently ran.
  final int minSources;

  final bool openInApp;

  static const defaults = Settings(
    weights: {
      'local': 1.5,
      'uk': 3.0,
      'ie': 0.5,
      'eu': 1.5,
      'us': 1.5,
      'world': 2.0,
    },
    locale: 'london',
    themeMode: ThemeMode.dark,
    textScale: 1.0,
    hours: 48,
    minSources: 1,
    openInApp: true,
  );

  Settings copyWith({
    Map<String, double>? weights,
    String? locale,
    ThemeMode? themeMode,
    double? textScale,
    int? hours,
    int? minSources,
    bool? openInApp,
  }) =>
      Settings(
        weights: weights ?? this.weights,
        locale: locale ?? this.locale,
        themeMode: themeMode ?? this.themeMode,
        textScale: textScale ?? this.textScale,
        hours: hours ?? this.hours,
        minSources: minSources ?? this.minSources,
        openInApp: openInApp ?? this.openInApp,
      );

  Map<String, dynamic> toJson() => {
        'weights': weights,
        'locale': locale,
        'themeMode': themeMode.name,
        'textScale': textScale,
        'hours': hours,
        'minSources': minSources,
        'openInApp': openInApp,
      };

  factory Settings.fromJson(Map<String, dynamic> j) => Settings(
        weights: ((j['weights'] ?? const {}) as Map)
            .map((k, v) => MapEntry(k as String, (v as num).toDouble())),
        locale: (j['locale'] ?? 'london') as String,
        themeMode: ThemeMode.values.firstWhere(
          (m) => m.name == (j['themeMode'] ?? 'dark'),
          orElse: () => ThemeMode.dark,
        ),
        textScale: ((j['textScale'] ?? 1.0) as num).toDouble(),
        hours: (j['hours'] ?? 48) as int,
        minSources: (j['minSources'] ?? 1) as int,
        openInApp: (j['openInApp'] ?? true) as bool,
      );
}

class SettingsController extends StateNotifier<Settings> {
  SettingsController() : super(Settings.defaults) {
    _load();
  }

  static const _key = 'newsfin.settings.v1';

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return;
    try {
      final loaded = Settings.fromJson(jsonDecode(raw) as Map<String, dynamic>);
      // Merge rather than replace, so a new region added in a later release
      // still gets a sensible default weight instead of vanishing.
      state = loaded.copyWith(
        weights: {...Settings.defaults.weights, ...loaded.weights},
      );
    } catch (_) {
      // Corrupt prefs should not brick the app.
    }
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(state.toJson()));
  }

  void setWeight(String region, double value) {
    state = state.copyWith(weights: {...state.weights, region: value});
    _save();
  }

  void setLocale(String locale) {
    state = state.copyWith(locale: locale);
    _save();
  }

  void setThemeMode(ThemeMode mode) {
    state = state.copyWith(themeMode: mode);
    _save();
  }

  void setTextScale(double scale) {
    state = state.copyWith(textScale: scale);
    _save();
  }

  void setHours(int hours) {
    state = state.copyWith(hours: hours);
    _save();
  }

  void setMinSources(int n) {
    state = state.copyWith(minSources: n);
    _save();
  }

  void setOpenInApp(bool v) {
    state = state.copyWith(openInApp: v);
    _save();
  }

  void resetWeights() {
    state = state.copyWith(weights: Settings.defaults.weights);
    _save();
  }
}

final settingsProvider =
    StateNotifierProvider<SettingsController, Settings>((ref) => SettingsController());

// ---------------------------------------------------------------------------
// Feeds
// ---------------------------------------------------------------------------

/// Identifies one scrollable list of stories.
@immutable
class FeedQuery {
  const FeedQuery({this.regions, this.topic, this.personalised = false});

  final List<String>? regions;
  final String? topic;

  /// Apply the reader's region weighting. True only for the Headlines tab -
  /// on a section tab the reader has already stated the region they want.
  final bool personalised;

  String get cacheKey =>
      'v1.${personalised ? 'me' : 'plain'}.${regions?.join('-') ?? 'all'}.${topic ?? 'top'}';

  @override
  bool operator ==(Object other) =>
      other is FeedQuery &&
      other.topic == topic &&
      other.personalised == personalised &&
      _sameList(other.regions, regions);

  static bool _sameList(List<String>? a, List<String>? b) {
    if (a == null || b == null) return a == b;
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  @override
  int get hashCode => Object.hash(topic, personalised, regions?.join('-'));
}

@immutable
class FeedState {
  const FeedState({
    this.stories = const [],
    this.loading = false,
    this.refreshing = false,
    this.error,
    this.generatedAt,
    this.fromCache = false,
    this.exhausted = false,
  });

  final List<Story> stories;
  final bool loading;
  final bool refreshing;
  final String? error;
  final DateTime? generatedAt;
  final bool fromCache;
  final bool exhausted;

  bool get isEmpty => stories.isEmpty;

  FeedState copyWith({
    List<Story>? stories,
    bool? loading,
    bool? refreshing,
    String? error,
    bool clearError = false,
    DateTime? generatedAt,
    bool? fromCache,
    bool? exhausted,
  }) =>
      FeedState(
        stories: stories ?? this.stories,
        loading: loading ?? this.loading,
        refreshing: refreshing ?? this.refreshing,
        error: clearError ? null : (error ?? this.error),
        generatedAt: generatedAt ?? this.generatedAt,
        fromCache: fromCache ?? this.fromCache,
        exhausted: exhausted ?? this.exhausted,
      );
}

class FeedController extends StateNotifier<FeedState> {
  FeedController(this._ref, this._query) : super(const FeedState(loading: true)) {
    _init();
  }

  final Ref _ref;
  final FeedQuery _query;
  static const _pageSize = 60;

  Future<void> _init() async {
    // Paint cached content first so the list is never empty on open, then
    // quietly replace it with live data.
    final cached = await FeedCache.read(_query.cacheKey);
    if (cached != null && mounted && state.stories.isEmpty) {
      state = state.copyWith(
        stories: cached.stories,
        loading: false,
        fromCache: true,
        generatedAt: cached.generatedAt,
      );
    }
    await load(silent: cached != null);
  }

  Future<void> load({bool silent = false}) async {
    if (!silent) {
      state = state.copyWith(loading: state.stories.isEmpty, refreshing: true);
    } else {
      state = state.copyWith(refreshing: true);
    }

    final settings = _ref.read(settingsProvider);
    try {
      final feed = await _ref.read(apiProvider).headlines(
            regions: _query.regions,
            topic: _query.topic,
            locale: _query.regions?.contains('local') ?? false ? settings.locale : null,
            weights: _query.personalised ? settings.weights : null,
            hours: settings.hours,
            minSources: settings.minSources,
            limit: _pageSize,
            cacheKey: _query.cacheKey,
          );
      if (!mounted) return;
      state = FeedState(
        stories: feed.stories,
        generatedAt: feed.generatedAt,
        exhausted: feed.stories.length < _pageSize,
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      // Keep whatever is on screen; an error banner beats a blank page.
      state = state.copyWith(
        loading: false,
        refreshing: false,
        error: e.message,
      );
    }
  }

  Future<void> loadMore() async {
    if (state.exhausted || state.refreshing || state.stories.isEmpty) return;
    final settings = _ref.read(settingsProvider);
    state = state.copyWith(refreshing: true);
    try {
      final feed = await _ref.read(apiProvider).headlines(
            regions: _query.regions,
            topic: _query.topic,
            locale: _query.regions?.contains('local') ?? false ? settings.locale : null,
            weights: _query.personalised ? settings.weights : null,
            hours: settings.hours,
            minSources: settings.minSources,
            limit: _pageSize,
            offset: state.stories.length,
          );
      if (!mounted) return;
      final seen = state.stories.map((s) => s.id).toSet();
      final fresh = feed.stories.where((s) => !seen.contains(s.id)).toList();
      state = state.copyWith(
        stories: [...state.stories, ...fresh],
        refreshing: false,
        exhausted: fresh.length < _pageSize,
        clearError: true,
      );
    } on ApiException {
      if (!mounted) return;
      state = state.copyWith(refreshing: false);
    }
  }

  Future<void> refresh() => load(silent: true);
}

final feedProvider =
    StateNotifierProvider.family<FeedController, FeedState, FeedQuery>(
  (ref, query) {
    // Re-fetch when the reader changes weighting or filters.
    ref.watch(settingsProvider.select((s) => (
          s.weights.toString(),
          s.locale,
          s.hours,
          s.minSources,
        )));
    return FeedController(ref, query);
  },
);

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

class SearchController extends StateNotifier<AsyncValue<List<Story>>> {
  SearchController(this._ref) : super(const AsyncValue.data([]));

  final Ref _ref;
  Timer? _debounce;
  String _last = '';

  void query(String q) {
    _debounce?.cancel();
    final trimmed = q.trim();
    if (trimmed.length < 2) {
      state = const AsyncValue.data([]);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 280), () async {
      _last = trimmed;
      state = const AsyncValue.loading();
      try {
        final results = await _ref.read(apiProvider).search(trimmed);
        // A slower earlier request must not overwrite a newer one.
        if (mounted && _last == trimmed) state = AsyncValue.data(results);
      } on ApiException catch (e, st) {
        if (mounted && _last == trimmed) state = AsyncValue.error(e.message, st);
      }
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }
}

final searchProvider =
    StateNotifierProvider<SearchController, AsyncValue<List<Story>>>(
        (ref) => SearchController(ref));
