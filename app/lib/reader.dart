/* MIT License - Copyright (c) fintonlabs.com */

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import 'models.dart';
import 'state.dart';

/// Reads the headlines aloud.
///
/// Built for someone who cannot comfortably read a phone screen at 6am, so it
/// is a genuine hands-free briefing rather than a screen-reader bolt-on: it
/// reads the ranked list in order, announces the corroboration count (which is
/// the part that says *why* a story is near the top), and keeps going until
/// stopped.
///
/// It deliberately does not fight VoiceOver or TalkBack. Those read the
/// interface; this reads the news.

/// The sentence spoken for one story.
///
/// Position first, because in a ranked list the number *is* the information -
/// a listener has no layout telling them this is the lead. The source count
/// trails the headline so the headline itself is never delayed, and it is
/// omitted entirely for a single-source story rather than saying "1 sources".
///
/// A top-level function, not a method, so the wording is testable without a
/// speech engine.
String spokenLine(Story story, int position, {required bool announceSources}) {
  final buffer = StringBuffer('$position. ${story.title}.');
  if (announceSources) {
    buffer.write(' ${story.source}');
    if (story.sources > 1) {
      buffer.write(', reported by ${story.sources} sources');
    }
    buffer.write('.');
  }
  return buffer.toString();
}

class ReaderState {
  const ReaderState({
    this.playing = false,
    this.index = 0,
    this.total = 0,
    this.currentTitle = '',
    this.available = true,
    this.error,
  });

  final bool playing;
  final int index;
  final int total;
  final String currentTitle;

  /// Only false once speech has actually been attempted and failed. It is
  /// deliberately not a startup capability probe - see the constructor.
  final bool available;

  final String? error;

  bool get active => playing || currentTitle.isNotEmpty;

  ReaderState copyWith({
    bool? playing,
    int? index,
    int? total,
    String? currentTitle,
    bool? available,
    String? error,
    bool clearError = false,
  }) =>
      ReaderState(
        playing: playing ?? this.playing,
        index: index ?? this.index,
        total: total ?? this.total,
        currentTitle: currentTitle ?? this.currentTitle,
        available: available ?? this.available,
        error: clearError ? null : (error ?? this.error),
      );
}

class ReaderController extends StateNotifier<ReaderState> {
  // No probing in the constructor.
  //
  // Browsers refuse speech synthesis until a user gesture has occurred, so a
  // startup probe fails on the web and used to mark the reader unavailable —
  // which hid the very button that would have supplied the gesture. The engine
  // is now initialised inside the tap that starts playback.
  ReaderController(this._ref) : super(const ReaderState());

  final Ref _ref;
  final FlutterTts _tts = FlutterTts();

  List<Story> _queue = const [];
  bool _ready = false;

  /// Guards against the completion handler advancing the queue after an
  /// explicit stop, which would otherwise restart playback a beat later.
  int _generation = 0;

  Future<void> _init() async {
    try {
      await _tts.setLanguage('en-GB');
      await _tts.setSpeechRate(_rateFor(_ref.read(settingsProvider).speechRate));
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);

      // On iOS the queue only behaves if we await each utterance.
      await _tts.awaitSpeakCompletion(true);

      _tts.setCompletionHandler(_onComplete);
      _tts.setErrorHandler((msg) {
        if (mounted) {
          state = state.copyWith(playing: false, error: 'Speech failed: $msg');
        }
      });
      _ready = true;
    } catch (e) {
      // Not fatal, and specifically not a reason to hide the control: some of
      // these setters are unimplemented on web, but speak() still works once a
      // gesture has happened. Only a failed speak() counts as unavailable.
      debugPrint('TTS setup incomplete (continuing): $e');
      _ready = true;
    }
  }

  /// flutter_tts rates are not comparable across platforms: 0.5 is normal on
  /// iOS/web, ~1.0 on Android. The reader stores a human multiplier and this
  /// maps it, so "Slow" means slow everywhere.
  double _rateFor(double multiplier) {
    final base = defaultTargetPlatform == TargetPlatform.android && !kIsWeb ? 1.0 : 0.5;
    return (base * multiplier).clamp(0.1, 1.6);
  }

  Future<void> start(List<Story> stories, {int from = 0}) async {
    if (stories.isEmpty) return;
    if (!_ready) await _init();

    _generation++;
    _queue = stories;
    state = state.copyWith(
      total: stories.length,
      index: from.clamp(0, stories.length - 1),
      playing: true,
      clearError: true,
    );
    await _speakCurrent();
  }

  Future<void> _speakCurrent() async {
    if (!mounted || _queue.isEmpty) return;
    final generation = _generation;
    final settings = _ref.read(settingsProvider);
    final story = _queue[state.index];

    state = state.copyWith(currentTitle: story.title);

    try {
      await _tts.setSpeechRate(_rateFor(settings.speechRate));
      await _tts.speak(
        spokenLine(story, state.index + 1,
            announceSources: settings.announceSources),
      );
      // awaitSpeakCompletion means we land here when the utterance finished,
      // so drive the queue from here rather than relying on the handler alone.
      if (mounted && generation == _generation && state.playing) {
        _advance();
      }
    } catch (e) {
      // A failure here is the real signal that this device cannot speak.
      if (mounted) {
        state = state.copyWith(
          playing: false,
          available: false,
          error: 'Speech is unavailable on this device',
        );
      }
      debugPrint('TTS speak failed: $e');
    }
  }

  void _onComplete() {
    // Platforms that ignore awaitSpeakCompletion still fire this.
    if (!mounted || !state.playing) return;
  }

  void _advance() {
    if (!mounted) return;
    if (state.index + 1 >= _queue.length) {
      stop();
      return;
    }
    state = state.copyWith(index: state.index + 1);
    _speakCurrent();
  }

  Future<void> next() async {
    if (_queue.isEmpty) return;
    _generation++;
    await _tts.stop();
    if (state.index + 1 >= _queue.length) return stop();
    state = state.copyWith(index: state.index + 1, playing: true);
    await _speakCurrent();
  }

  Future<void> previous() async {
    if (_queue.isEmpty) return;
    _generation++;
    await _tts.stop();
    state = state.copyWith(
      index: (state.index - 1).clamp(0, _queue.length - 1),
      playing: true,
    );
    await _speakCurrent();
  }

  Future<void> pause() async {
    _generation++;
    await _tts.stop();
    if (mounted) state = state.copyWith(playing: false);
  }

  Future<void> resume() async {
    if (_queue.isEmpty) return;
    state = state.copyWith(playing: true);
    await _speakCurrent();
  }

  Future<void> toggle(List<Story> stories) async {
    if (state.playing) return pause();
    if (state.currentTitle.isNotEmpty && _queue.isNotEmpty) return resume();
    return start(stories);
  }

  Future<void> stop() async {
    _generation++;
    await _tts.stop();
    if (mounted) {
      state = state.copyWith(playing: false, currentTitle: '', index: 0);
    }
  }

  /// The story currently being read, so tapping the reader bar opens it.
  Story? get currentStory =>
      _queue.isEmpty || state.index >= _queue.length ? null : _queue[state.index];

  @override
  void dispose() {
    _tts.stop();
    super.dispose();
  }
}

final readerProvider =
    StateNotifierProvider<ReaderController, ReaderState>((ref) => ReaderController(ref));
