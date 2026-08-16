import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

/// Where the API lives.
///
/// The web build is served by the same FastAPI process that serves the API, so
/// it uses a relative origin and works on any host without a rebuild. Native
/// builds point at the deployed host unless overridden with
/// `--dart-define=NEWSFIN_API=http://192.168.1.10:8099` for local testing.
const _override = String.fromEnvironment('NEWSFIN_API');

String get apiBase {
  if (_override.isNotEmpty) return _override;
  if (kIsWeb) return '';
  return 'https://newsfin.apps.fintonlabs.com';
}

class ApiException implements Exception {
  ApiException(this.message);
  final String message;
  @override
  String toString() => message;
}

class NewsApi {
  NewsApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  static const _timeout = Duration(seconds: 20);

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = apiBase;
    final q = (query == null || query.isEmpty) ? '' : '?${Uri(queryParameters: query).query}';
    return Uri.parse('$base$path$q');
  }

  Future<Map<String, dynamic>> _getJson(String path, [Map<String, String>? query]) async {
    final uri = _uri(path, query);
    try {
      final res = await _client.get(uri, headers: {
        'Accept': 'application/json',
      }).timeout(_timeout);
      if (res.statusCode != 200) {
        throw ApiException('Server returned ${res.statusCode}');
      }
      return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    } on TimeoutException {
      throw ApiException('Timed out reaching the news service');
    } on http.ClientException catch (e) {
      throw ApiException('Network unavailable (${e.message})');
    }
  }

  Future<AppConfig> config() async {
    try {
      return AppConfig.fromJson(await _getJson('/api/v1/config'));
    } on ApiException {
      return AppConfig.fallback;
    }
  }

  Future<HeadlineFeed> headlines({
    List<String>? regions,
    String? topic,
    String? locale,
    Map<String, double>? weights,
    int hours = 48,
    int limit = 60,
    int offset = 0,
    int minSources = 1,
    String sort = 'top',
    String? cacheKey,
  }) async {
    final q = <String, String>{
      'hours': '$hours',
      'limit': '$limit',
      'offset': '$offset',
      'min_sources': '$minSources',
      'coverage': 'true',
      'sort': sort,
    };
    if (regions != null && regions.isNotEmpty) q['regions'] = regions.join(',');
    if (topic != null && topic != 'top') q['topic'] = topic;
    if (locale != null && locale.isNotEmpty) q['locale'] = locale;
    if (weights != null && weights.isNotEmpty) {
      q['weights'] =
          weights.entries.map((e) => '${e.key}:${e.value.toStringAsFixed(2)}').join(',');
    }
    final json = await _getJson('/api/v1/headlines', q);
    if (cacheKey != null && offset == 0) {
      // Fire and forget - a cache write must never delay rendering.
      unawaited(FeedCache.write(cacheKey, json));
    }
    return HeadlineFeed.fromJson(json);
  }

  Future<List<Story>> search(String query) async {
    final j = await _getJson('/api/v1/search', {'q': query, 'limit': '60'});
    return ((j['stories'] ?? const []) as List)
        .map((e) => Story.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> stats() => _getJson('/api/v1/stats');
}

/// Last successful payload per tab, so the app opens with content on screen
/// before the network answers. At 6am on a train that is the difference
/// between a usable app and a spinner.
class FeedCache {
  static const _prefix = 'newsfin.cache.';
  static const _maxAge = Duration(hours: 6);

  static Future<void> write(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_prefix$key', jsonEncode({
      'at': DateTime.now().toIso8601String(),
      'payload': payload,
    }));
  }

  static Future<HeadlineFeed?> read(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_prefix$key');
    if (raw == null) return null;
    try {
      final wrapper = jsonDecode(raw) as Map<String, dynamic>;
      final at = DateTime.tryParse(wrapper['at'] as String? ?? '');
      if (at == null || DateTime.now().difference(at) > _maxAge) return null;
      return HeadlineFeed.fromJson(wrapper['payload'] as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }
}
