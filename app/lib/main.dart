import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:url_launcher/url_launcher.dart';

import 'models.dart';
import 'reader.dart';
import 'screens/headlines.dart';
import 'screens/search.dart';
import 'screens/sections.dart';
import 'screens/settings.dart';
import 'state.dart';
import 'theme.dart';
import 'widgets/reader_bar.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  runApp(const ProviderScope(child: NewsFinApp()));
}

class NewsFinApp extends ConsumerWidget {
  const NewsFinApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);
    final platformBrightness = MediaQuery.platformBrightnessOf(context);
    final brightness = switch (settings.themeMode) {
      ThemeMode.dark => Brightness.dark,
      ThemeMode.light => Brightness.light,
      ThemeMode.system => platformBrightness,
    };
    final colors = brightness == Brightness.dark ? NewsColors.dark : NewsColors.light;

    return MaterialApp(
      title: 'NewsFin',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(NewsColors.light, Brightness.light),
      darkTheme: buildTheme(NewsColors.dark, Brightness.dark),
      themeMode: settings.themeMode,
      builder: (context, child) => NewsTheme(
        colors: colors,
        child: MediaQuery.withClampedTextScaling(
          // Respect the reader's own choice, but keep the system scale from
          // breaking a layout built on a typographic grid.
          minScaleFactor: settings.textScale,
          maxScaleFactor: settings.textScale,
          child: AnnotatedRegion<SystemUiOverlayStyle>(
            value: overlayFor(brightness),
            child: child ?? const SizedBox.shrink(),
          ),
        ),
      ),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> with WidgetsBindingObserver {
  int _index = 0;
  DateTime _backgroundedAt = DateTime.now();

  /// Tabs that have been opened at least once. Everything else stays unbuilt,
  /// so a cold start does the work of one screen rather than four.
  final Set<int> _visited = {0};

  void _select(int i) {
    setState(() {
      _index = i;
      _visited.add(i);
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Coming back to the app after a while should show current news, not
    // whatever was on screen when it was last put down.
    if (state == AppLifecycleState.paused) {
      _backgroundedAt = DateTime.now();
      // Speech continuing after the app is backgrounded is disorienting and
      // there is no lock-screen control for it.
      ref.read(readerProvider.notifier).pause();
    } else if (state == AppLifecycleState.resumed) {
      final away = DateTime.now().difference(_backgroundedAt);
      if (away > const Duration(minutes: 4)) {
        ref.read(feedProvider(const FeedQuery(personalised: true)).notifier).refresh();
      }
    }
  }

  Future<void> _openStory(Story story) async {
    final uri = Uri.tryParse(story.url);
    if (uri == null) return;
    final mode = ref.read(settingsProvider).openInApp
        ? LaunchMode.inAppBrowserView
        : LaunchMode.externalApplication;
    try {
      await launchUrl(uri, mode: mode);
    } catch (_) {
      await launchUrl(uri, mode: LaunchMode.platformDefault);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);

    // IndexedStack builds every child, so the stock version mounted all four
    // tabs on the first frame: Sections immediately fired its own headlines
    // request and built a second 60-row list nobody had asked for. That is
    // what made the app slow to answer the first tap.
    //
    // A tab is built the first time it is opened and kept alive after that, so
    // switching back stays instant.
    Widget tabAt(int i) {
      if (!_visited.contains(i)) return const SizedBox.shrink();
      return switch (i) {
        0 => HeadlinesScreen(onOpenSettings: () => _select(3)),
        1 => const SectionsScreen(),
        2 => const SearchScreen(),
        _ => const SettingsScreen(),
      };
    }

    return Scaffold(
      backgroundColor: c.canvas,
      // Phone-first, but the PWA opens on laptops too - the measure is capped
      // so headlines never run the full width of a desktop display.
      body: Measure(
        child: IndexedStack(
          index: _index,
          children: [for (var i = 0; i < 4; i++) tabAt(i)],
        ),
      ),
      bottomNavigationBar: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Above the nav so it never covers the last row of a list.
          ReaderBar(onOpen: _openStory),
          _BottomBar(
            index: _index,
            onChanged: (i) {
              HapticFeedback.selectionClick();
              _select(i);
            },
          ),
        ],
      ),
    );
  }
}

/// Custom bar rather than NavigationBar: the stock Material bar brings pill
/// indicators and a 80px height that fight the typographic scale used
/// everywhere else in the app.
class _BottomBar extends StatelessWidget {
  const _BottomBar({required this.index, required this.onChanged});

  final int index;
  final ValueChanged<int> onChanged;

  static const _items = [
    (Icons.article_outlined, Icons.article_rounded, 'Headlines'),
    (Icons.public_outlined, Icons.public_rounded, 'Sections'),
    (Icons.search_rounded, Icons.search_rounded, 'Search'),
    (Icons.tune_outlined, Icons.tune_rounded, 'Settings'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: c.canvas,
        border: Border(top: BorderSide(color: c.hairline)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 56,
          child: Measure(
              child: Row(
            children: [
              for (var i = 0; i < _items.length; i++)
                Expanded(
                  child: InkWell(
                    onTap: () => onChanged(i),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          i == index ? _items[i].$2 : _items[i].$1,
                          size: 21,
                          color: i == index ? c.accent : c.textTertiary,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _items[i].$3.toUpperCase(),
                          style: NewsType.eyebrow.copyWith(
                            fontSize: 8.5,
                            color: i == index ? c.textPrimary : c.textTertiary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          )),
        ),
      ),
    );
  }
}
