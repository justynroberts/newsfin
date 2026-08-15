import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models.dart';
import '../motion.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/chrome.dart';
import '../widgets/coverage_sheet.dart';
import '../widgets/story_tile.dart';

/// One scrollable section of headlines.
///
/// The layout follows a front page rather than a feed: the top story gets
/// real size, the next few are grouped under a rule, and the rest run as an
/// even list. That variation is what stops 60 headlines reading as a wall.
class FeedList extends ConsumerStatefulWidget {
  const FeedList({
    super.key,
    required this.query,
    this.sectionLabel,
    this.header,
  });

  final FeedQuery query;
  final String? sectionLabel;
  final Widget? header;

  @override
  ConsumerState<FeedList> createState() => _FeedListState();
}

class _FeedListState extends ConsumerState<FeedList>
    with AutomaticKeepAliveClientMixin {
  final _scroll = ScrollController();

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_maybeLoadMore);
  }

  void _maybeLoadMore() {
    if (!_scroll.hasClients) return;
    final remaining = _scroll.position.maxScrollExtent - _scroll.position.pixels;
    if (remaining < 1200) {
      ref.read(feedProvider(widget.query).notifier).loadMore();
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _open(String url) async {
    final settings = ref.read(settingsProvider);
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    // inAppBrowserView is SFSafariViewController / Chrome Custom Tabs - it
    // keeps the reader inside the app with a native chrome, which is what
    // every good news app does. Falling back to the system browser matters
    // for the web build, where custom tabs do not exist.
    final mode = settings.openInApp
        ? LaunchMode.inAppBrowserView
        : LaunchMode.externalApplication;
    try {
      final ok = await launchUrl(uri, mode: mode);
      if (!ok) await launchUrl(uri, mode: LaunchMode.platformDefault);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not open $url')),
      );
    }
  }

  void _showCoverage(Story story) {
    CoverageSheet.show(context, story, _open);
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final c = NewsTheme.of(context);
    final state = ref.watch(feedProvider(widget.query));
    final controller = ref.read(feedProvider(widget.query).notifier);

    if (state.loading && state.isEmpty) {
      return ListView(
        children: [
          if (widget.header != null) widget.header!,
          const HeadlineSkeleton(),
        ],
      );
    }

    if (state.isEmpty) {
      return RefreshIndicator(
        onRefresh: controller.refresh,
        color: c.accent,
        backgroundColor: c.surface,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            if (widget.header != null) widget.header!,
            SizedBox(
              height: 380,
              child: NoticePanel(
                icon: state.error != null
                    ? Icons.wifi_off_rounded
                    : Icons.filter_alt_off_rounded,
                title: state.error != null ? 'Cannot reach the news' : 'Nothing here yet',
                body: state.error ??
                    'No stories match this section and your current filters. '
                        'Try widening the time window in Settings.',
                actionLabel: 'Try again',
                onAction: controller.refresh,
              ),
            ),
          ],
        ),
      );
    }

    final stories = state.stories;
    final lead = stories.first;
    final rest = stories.skip(1).toList();

    return RefreshIndicator(
      onRefresh: controller.refresh,
      color: c.accent,
      backgroundColor: c.surface,
      displacement: 28,
      child: CustomScrollView(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          if (widget.header != null) SliverToBoxAdapter(child: widget.header!),
          if (state.error != null)
            SliverToBoxAdapter(
              child: StaleBanner(
                message: state.fromCache
                    ? 'Showing saved headlines - ${state.error}'
                    : state.error!,
                onRetry: controller.refresh,
              ),
            ),
          SliverToBoxAdapter(
            child: RiseIn(
              child: LeadStory(
                story: lead,
                label: widget.sectionLabel,
                onTap: () => _open(lead.url),
                onCoverage: () => _showCoverage(lead),
              ),
            ),
          ),
          SliverList.separated(
            itemCount: rest.length,
            separatorBuilder: (_, __) => const StoryDivider(),
            itemBuilder: (context, i) {
              final story = rest[i];
              // A quiet section break every ten rows gives the eye somewhere
              // to rest and makes a long list feel navigable.
              // The stagger index restarts past the first screenful, so rows
              // reached by scrolling animate on their own rather than
              // inheriting a long queue delay from the top of the list.
              final tile = StoryTile(
                story: story,
                onTap: () => _open(story.url),
                onCoverage: () => _showCoverage(story),
              );
              if (i > 0 && i % 10 == 0) {
                return RiseIn(
                  index: i % 10,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [_RunningHead(index: i), tile],
                  ),
                );
              }
              return RiseIn(index: i % 10 + 1, child: tile);
            },
          ),
          SliverToBoxAdapter(
            child: _FeedFooter(
              generatedAt: state.generatedAt,
              loading: state.refreshing,
              exhausted: state.exhausted,
              count: stories.length,
            ),
          ),
        ],
      ),
    );
  }
}

class _RunningHead extends StatelessWidget {
  const _RunningHead({required this.index});

  final int index;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final label = switch (index) {
      10 => 'ALSO TODAY',
      20 => 'MORE COVERAGE',
      30 => 'FURTHER READING',
      _ => 'CONTINUED',
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(Gap.page, Gap.xl, Gap.page, Gap.sm),
      child: Row(
        children: [
          Text(label, style: NewsType.eyebrow.copyWith(color: c.textTertiary)),
          const SizedBox(width: Gap.md),
          Expanded(child: Container(height: 1, color: c.hairline)),
        ],
      ),
    );
  }
}

class _FeedFooter extends StatelessWidget {
  const _FeedFooter({
    required this.generatedAt,
    required this.loading,
    required this.exhausted,
    required this.count,
  });

  final DateTime? generatedAt;
  final bool loading;
  final bool exhausted;
  final int count;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        Gap.page,
        Gap.xxl,
        Gap.page,
        MediaQuery.of(context).padding.bottom + Gap.xxl,
      ),
      child: Column(
        children: [
          if (loading && !exhausted)
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 1.6, color: c.textTertiary),
            )
          else ...[
            Container(width: 28, height: 1, color: c.hairlineStrong),
            const SizedBox(height: Gap.md),
            Text(
              exhausted ? 'END OF SECTION' : 'LOADING MORE',
              style: NewsType.eyebrow.copyWith(color: c.textTertiary, fontSize: 9.5),
            ),
            const SizedBox(height: Gap.sm),
            Text(
              '$count stories · ranked by impact',
              style: NewsType.meta.copyWith(color: c.textTertiary),
            ),
          ],
        ],
      ),
    );
  }
}
