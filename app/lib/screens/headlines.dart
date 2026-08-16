import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../state.dart';
import '../theme.dart';
import '../widgets/chrome.dart';
import '../widgets/reader_bar.dart';
import 'feed_list.dart';

/// The tab this app exists for.
///
/// One blended, impact-ranked list drawn from every region, reweighted by what
/// the reader said matters to them. Open it at 6am and the top of the list is
/// the day, not whatever a single outlet published most recently.
class HeadlinesScreen extends ConsumerStatefulWidget {
  const HeadlinesScreen({super.key, required this.onOpenSettings});

  final VoidCallback onOpenSettings;

  @override
  ConsumerState<HeadlinesScreen> createState() => _HeadlinesScreenState();
}

class _HeadlinesScreenState extends ConsumerState<HeadlinesScreen> {
  FeedSort _sort = FeedSort.top;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final settings = ref.watch(settingsProvider);
    final now = DateTime.now();

    final active = settings.weights.entries
        .where((e) => e.value > 0)
        .map((e) => e.key)
        .toList()
      ..sort((a, b) => settings.weights[b]!.compareTo(settings.weights[a]!));

    final query = FeedQuery(personalised: true, sort: _sort);

    return SafeArea(
      bottom: false,
      child: FeedList(
        key: ValueKey('headlines.${_sort.wire}'),
        query: query,
        sectionLabel: _sort == FeedSort.latest ? 'Latest' : _greeting(now),
        header: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Masthead(
              dateline: DateFormat('EEEE d MMMM').format(now),
              trailing: ListenButton(
                stories: ref.watch(feedProvider(query).select((s) => s.stories)),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, Gap.md),
              child: Row(
                children: [
                  Text(
                    'YOUR MIX',
                    style: NewsType.eyebrow.copyWith(color: c.textTertiary, fontSize: 9.5),
                  ),
                  const SizedBox(width: Gap.md),
                  Expanded(
                    child: Text(
                      active
                          .take(3)
                          .map((r) => _regionLabel(r).toUpperCase())
                          .join('  ·  '),
                      style: NewsType.eyebrow.copyWith(color: c.textSecondary, fontSize: 9.5),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  _WeightButton(onTap: widget.onOpenSettings),
                ],
              ),
            ),
            Container(height: 1, color: c.hairline),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: Gap.page - 9),
              child: Row(
                children: [
                  LaneSwitch(
                    sort: _sort,
                    onChanged: (s) => setState(() => _sort = s),
                  ),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.only(right: 9),
                    child: Text(
                      _sort == FeedSort.latest
                          ? 'NEWEST FIRST'
                          : 'RANKED BY IMPACT',
                      style: NewsType.eyebrow
                          .copyWith(color: c.textTertiary, fontSize: 9),
                    ),
                  ),
                ],
              ),
            ),
            Container(height: 1, color: c.hairline),
          ],
        ),
      ),
    );
  }

  /// A morning app should acknowledge the morning.
  String _greeting(DateTime now) {
    final h = now.hour;
    if (h < 5) return 'Overnight';
    if (h < 12) return 'This morning';
    if (h < 18) return 'This afternoon';
    return 'This evening';
  }

  String _regionLabel(String key) => switch (key) {
        'local' => 'Local',
        'uk' => 'UK',
        'ie' => 'Ireland',
        'eu' => 'Europe',
        'us' => 'US',
        'world' => 'World',
        _ => key,
      };
}

class _WeightButton extends StatelessWidget {
  const _WeightButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: Gap.md, vertical: Gap.sm),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: c.hairline),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.tune_rounded, size: 13, color: c.textSecondary),
            const SizedBox(width: 6),
            Text(
              'MIX',
              style: NewsType.eyebrow.copyWith(color: c.textSecondary, fontSize: 9.5),
            ),
          ],
        ),
      ),
    );
  }
}
