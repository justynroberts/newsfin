/* MIT License - Copyright (c) fintonlabs.com */

import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

/// Learns what you actually read, on the device, and nudges the ranking.
///
/// Three things make this different from the usual recommendation feed:
///
/// **It measures lift, not volume.** Counting opens per topic would just
/// rediscover the shape of the feed - most headlines are general news, so most
/// opens are too. What matters is whether you open Tech *more often than it is
/// shown to you*. So impressions are counted alongside opens and the ratio is
/// compared against your own overall rate.
///
/// **It cannot bury the news.** The multiplier is clamped, and a story carried
/// by many independent newsrooms is exempt outright. If thirty newsrooms are
/// running something, no amount of "you usually skip world news" should push it
/// off your morning. That is the whole premise of the app and personalisation
/// does not get to overrule it.
///
/// **It never leaves the device.** No profile is uploaded, and there is no
/// account to attach it to. It lives in local storage and a single button
/// erases it.

/// A recency-weighted tally. Every observation decays what came before, so a
/// month of reading habits does not outweigh this week's.
class _Counter {
  _Counter([Map<String, double>? seed]) : _values = {...?seed};

  final Map<String, double> _values;

  /// Applied to existing weight on each observation. At 0.997 an interest
  /// halves after roughly 230 events - a few weeks of ordinary reading.
  static const _decay = 0.997;

  void add(String key, double weight) {
    if (weight <= 0) return;
    for (final k in _values.keys) {
      _values[k] = _values[k]! * _decay;
    }
    _values[key] = (_values[key] ?? 0) + weight;
    // Keep the map from growing without bound as outlets come and go.
    if (_values.length > 400) {
      final ordered = _values.entries.toList()
        ..sort((a, b) => b.value.compareTo(a.value));
      _values
        ..clear()
        ..addEntries(ordered.take(200));
    }
  }

  double operator [](String key) => _values[key] ?? 0;
  double get total => _values.values.fold(0.0, (a, b) => a + b);
  Map<String, double> get raw => Map.unmodifiable(_values);
}

@immutable
class TasteState {
  const TasteState({
    required this.enabled,
    required this.topicOpens,
    required this.topicShown,
    required this.sourceOpens,
    required this.sourceShown,
    required this.opens,
  });

  final bool enabled;
  final Map<String, double> topicOpens;
  final Map<String, double> topicShown;
  final Map<String, double> sourceOpens;
  final Map<String, double> sourceShown;

  /// Total stories opened. Used only to decide whether there is enough
  /// evidence to act on at all.
  final int opens;

  static const empty = TasteState(
    enabled: true,
    topicOpens: {},
    topicShown: {},
    sourceOpens: {},
    sourceShown: {},
    opens: 0,
  );

  /// Below this the profile is ignored entirely. Reranking on three data
  /// points would be noise dressed up as insight.
  static const minimumOpens = 12;

  bool get ready => enabled && opens >= minimumOpens;

  Map<String, dynamic> toJson() => {
        'enabled': enabled,
        'topicOpens': topicOpens,
        'topicShown': topicShown,
        'sourceOpens': sourceOpens,
        'sourceShown': sourceShown,
        'opens': opens,
      };

  static Map<String, double> _readMap(dynamic v) => ((v ?? const {}) as Map)
      .map((k, x) => MapEntry(k as String, (x as num).toDouble()));

  factory TasteState.fromJson(Map<String, dynamic> j) => TasteState(
        enabled: (j['enabled'] ?? true) as bool,
        topicOpens: _readMap(j['topicOpens']),
        topicShown: _readMap(j['topicShown']),
        sourceOpens: _readMap(j['sourceOpens']),
        sourceShown: _readMap(j['sourceShown']),
        opens: (j['opens'] ?? 0) as int,
      );
}

/// How strongly a preference is allowed to move a story.
///
/// Deliberately narrow. At 1.25 a favoured story climbs a few places among
/// near-equals; it cannot leapfrog a genuinely bigger story.
const double _maxLift = 1.25;
const double _minLift = 0.8;

/// A story carried by this many independent newsrooms is never demoted,
/// whatever the profile says.
const int _protectedSources = 8;

/// Evidence needed before a single topic or outlet is trusted.
const double _minShown = 8;

double _lift(double opens, double shown, double baseline) {
  if (shown < _minShown || baseline <= 0) return 1.0;
  final rate = opens / shown;
  return (rate / baseline).clamp(_minLift, _maxLift);
}

class TasteController extends StateNotifier<TasteState> {
  TasteController() : super(TasteState.empty) {
    _load();
  }

  static const _key = 'newsfin.taste.v1';

  final _topicOpens = _Counter();
  final _topicShown = _Counter();
  final _sourceOpens = _Counter();
  final _sourceShown = _Counter();

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return;
    try {
      final loaded = TasteState.fromJson(jsonDecode(raw) as Map<String, dynamic>);
      _topicOpens._values.addAll(loaded.topicOpens);
      _topicShown._values.addAll(loaded.topicShown);
      _sourceOpens._values.addAll(loaded.sourceOpens);
      _sourceShown._values.addAll(loaded.sourceShown);
      state = loaded;
    } catch (_) {
      // A corrupt profile is not worth crashing over; start again.
    }
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(state.toJson()));
  }

  void _publish({int? opens}) {
    state = TasteState(
      enabled: state.enabled,
      topicOpens: _topicOpens.raw,
      topicShown: _topicShown.raw,
      sourceOpens: _sourceOpens.raw,
      sourceShown: _sourceShown.raw,
      opens: opens ?? state.opens,
    );
    _save();
  }

  /// The strongest signal there is: you chose to read it.
  void recordOpen(Story story) {
    if (!state.enabled) return;
    for (final topic in story.topics) {
      _topicOpens.add(topic, 1);
    }
    _sourceOpens.add(story.source, 1);
    _publish(opens: state.opens + 1);
  }

  /// Opening the coverage sheet is interest, but weaker than reading - you
  /// were curious about the story, not committed to it.
  void recordInspect(Story story) {
    if (!state.enabled) return;
    for (final topic in story.topics) {
      _topicOpens.add(topic, 0.3);
    }
    _sourceOpens.add(story.source, 0.3);
    _publish();
  }

  /// What you were offered. Without this the profile would only rediscover
  /// which topics the feed publishes most of.
  void recordShown(List<Story> stories) {
    if (!state.enabled || stories.isEmpty) return;
    for (final story in stories) {
      for (final topic in story.topics) {
        _topicShown.add(topic, 1);
      }
      _sourceShown.add(story.source, 1);
    }
    _publish();
  }

  void setEnabled(bool value) {
    state = TasteState(
      enabled: value,
      topicOpens: state.topicOpens,
      topicShown: state.topicShown,
      sourceOpens: state.sourceOpens,
      sourceShown: state.sourceShown,
      opens: state.opens,
    );
    _save();
  }

  Future<void> forget() async {
    _topicOpens._values.clear();
    _topicShown._values.clear();
    _sourceOpens._values.clear();
    _sourceShown._values.clear();
    state = TasteState(
      enabled: state.enabled,
      topicOpens: const {},
      topicShown: const {},
      sourceOpens: const {},
      sourceShown: const {},
      opens: 0,
    );
    await _save();
  }
}

final tasteProvider =
    StateNotifierProvider<TasteController, TasteState>((ref) => TasteController());

/// Pure scoring, kept out of the controller so it is testable without storage.
class Taste {
  const Taste(this.state);

  final TasteState state;

  double get _topicBaseline {
    final shown = state.topicShown.values.fold(0.0, (a, b) => a + b);
    final opens = state.topicOpens.values.fold(0.0, (a, b) => a + b);
    return shown <= 0 ? 0 : opens / shown;
  }

  double get _sourceBaseline {
    final shown = state.sourceShown.values.fold(0.0, (a, b) => a + b);
    final opens = state.sourceOpens.values.fold(0.0, (a, b) => a + b);
    return shown <= 0 ? 0 : opens / shown;
  }

  /// Lift for one topic: how much more often you open it than you open
  /// anything. 1.0 means "no different from your average".
  double topicLift(String topic) => _lift(
        state.topicOpens[topic] ?? 0,
        state.topicShown[topic] ?? 0,
        _topicBaseline,
      );

  double sourceLift(String source) => _lift(
        state.sourceOpens[source] ?? 0,
        state.sourceShown[source] ?? 0,
        _sourceBaseline,
      );

  /// The multiplier applied to a story's rank score.
  double multiplierFor(Story story) {
    if (!state.ready) return 1.0;

    final topics = story.topics.where((t) => t != 'top').toList();
    final topicPart = topics.isEmpty
        ? 1.0
        : topics.map(topicLift).reduce((a, b) => a + b) / topics.length;
    final sourcePart = sourceLift(story.source);

    // The outlet counts for less than the subject: reading three BBC pieces
    // says more about the BBC's output than about you.
    final blended = 0.65 * topicPart + 0.35 * sourcePart;

    // Widely corroborated news is never pushed down. This is the guarantee
    // that keeps the app an impact ranking rather than a taste bubble.
    if (story.sources >= _protectedSources) return math.max(1.0, blended);

    return blended.clamp(_minLift, _maxLift);
  }

  /// Reorders one lane. Stable: equal scores keep the server's order, so this
  /// only ever nudges.
  List<Story> rerank(List<Story> stories) {
    if (!state.ready) return stories;
    final indexed = stories.indexed.toList();
    indexed.sort((a, b) {
      final sa = (a.$2.impact) * multiplierFor(a.$2);
      final sb = (b.$2.impact) * multiplierFor(b.$2);
      final cmp = sb.compareTo(sa);
      return cmp != 0 ? cmp : a.$1.compareTo(b.$1);
    });
    return [for (final e in indexed) e.$2];
  }

  /// What the profile has actually learned, strongest first - for showing the
  /// reader rather than for scoring. Personalisation you cannot inspect is
  /// just a black box deciding what you see.
  List<({String label, double lift})> learnedTopics() {
    final out = <({String label, double lift})>[];
    for (final topic in state.topicShown.keys) {
      if (topic == 'top') continue;
      final lift = topicLift(topic);
      if ((lift - 1.0).abs() < 0.04) continue;
      out.add((label: topic, lift: lift));
    }
    out.sort((a, b) => b.lift.compareTo(a.lift));
    return out;
  }
}
