import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/chrome.dart';
import 'feed_list.dart';

/// Region and topic browsing.
///
/// Two rails: the region rail picks the geography, the topic rail filters
/// within it. Both are swipeable, because a news app that makes you tap to
/// change section feels slow no matter how fast it loads.
class SectionsScreen extends ConsumerStatefulWidget {
  const SectionsScreen({super.key});

  @override
  ConsumerState<SectionsScreen> createState() => _SectionsScreenState();
}

class _SectionsScreenState extends ConsumerState<SectionsScreen>
    with SingleTickerProviderStateMixin {
  late PageController _pages;
  int _regionIndex = 0;
  String _topic = 'top';
  FeedSort _sort = FeedSort.latest;

  @override
  void initState() {
    super.initState();
    _pages = PageController();
  }

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final config = ref.watch(configProvider).valueOrNull ?? AppConfig.fallback;
    final regions = config.regions;
    final topics = config.topics;
    final settings = ref.watch(settingsProvider);

    final localeLabel = config.locales
        .where((l) => l.key == settings.locale)
        .map((l) => l.label)
        .firstOrNull;

    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          Masthead(
            dateline: 'Sections',
            subtitle: 'Browse by region and topic',
          ),
          SectionRail(
            labels: [
              for (final r in regions)
                r.key == 'local' && localeLabel != null ? localeLabel : r.label,
            ],
            index: _regionIndex,
            onChanged: (i) {
              setState(() => _regionIndex = i);
              _pages.animateToPage(
                i,
                duration: const Duration(milliseconds: 280),
                curve: Curves.easeOutCubic,
              );
            },
          ),
          _TopicRail(
            topics: topics,
            selected: _topic,
            onChanged: (t) {
              HapticFeedback.selectionClick();
              setState(() => _topic = t);
            },
            lane: LaneSwitch(
              sort: _sort,
              onChanged: (s) => setState(() => _sort = s),
            ),
          ),
          Expanded(
            child: PageView.builder(
              controller: _pages,
              itemCount: regions.length,
              onPageChanged: (i) => setState(() => _regionIndex = i),
              itemBuilder: (context, i) {
                final region = regions[i];
                return FeedList(
                  key: ValueKey(
                    '${region.key}.$_topic.${settings.locale}.${_sort.wire}',
                  ),
                  query: FeedQuery(
                    regions: [region.key],
                    topic: _topic,
                    sort: _sort,
                  ),
                  sectionLabel: _topic == 'top'
                      ? (region.key == 'local' ? localeLabel ?? region.label : region.label)
                      : '${region.label} · ${topics.firstWhere((t) => t.key == _topic, orElse: () => const Section('top', 'Top')).label}',
                );
              },
            ),
          ),
        ],
      ),
    ).withBackground(c);
  }
}

/// Topic filter. Pills here rather than underlines - it is a *filter* applied
/// on top of the region rail, and it should read as a different kind of
/// control from the section navigation above it.
class _TopicRail extends StatelessWidget {
  const _TopicRail({
    required this.topics,
    required this.selected,
    required this.onChanged,
    required this.lane,
  });

  final List<Section> topics;
  final String selected;
  final ValueChanged<String> onChanged;

  /// Pinned beside the scrolling topics so the lane is always reachable
  /// without scrolling the filter rail back to the start.
  final Widget lane;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Container(
      height: 46,
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: c.hairline)),
      ),
      child: Row(
        children: [
          Expanded(
            child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Gap.page, vertical: Gap.sm),
        itemCount: topics.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, i) {
          final t = topics[i];
          final active = t.key == selected;
          return GestureDetector(
            onTap: () => onChanged(t.key),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              padding: const EdgeInsets.symmetric(horizontal: 12),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: active ? c.textPrimary : Colors.transparent,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: active ? c.textPrimary : c.hairline),
              ),
              child: Text(
                t.label,
                style: NewsType.meta.copyWith(
                  color: active ? c.canvas : c.textSecondary,
                  fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ),
              );
            },
          ),
        ),
        Container(width: 1, height: 26, color: c.hairline),
        Padding(
          padding: const EdgeInsets.only(left: 4, right: Gap.page - 9),
          child: lane,
        ),
      ]),
    );
  }
}

extension on Widget {
  Widget withBackground(NewsColors c) => ColoredBox(color: c.canvas, child: this);
}
