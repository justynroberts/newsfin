import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models.dart';
import '../state.dart';
import '../theme.dart';
import 'about.dart';

/// Horizontally scrolling section strip.
///
/// Underline rather than pills. Pills are an app convention; an underlined
/// section rail is what every serious news front end uses, and it keeps the
/// labels themselves as the visual anchor instead of a row of coloured blobs.
class SectionRail extends StatefulWidget {
  const SectionRail({
    super.key,
    required this.labels,
    required this.index,
    required this.onChanged,
  });

  final List<String> labels;
  final int index;
  final ValueChanged<int> onChanged;

  @override
  State<SectionRail> createState() => _SectionRailState();
}

class _SectionRailState extends State<SectionRail> {
  final _controller = ScrollController();
  final _keys = <int, GlobalKey>{};

  @override
  void didUpdateWidget(SectionRail old) {
    super.didUpdateWidget(old);
    if (old.index != widget.index) _scrollTo(widget.index);
  }

  /// Keep the active section on screen when it changes by swipe rather than
  /// by tap - otherwise the rail silently desyncs from the page.
  void _scrollTo(int index) {
    final key = _keys[index];
    final ctx = key?.currentContext;
    if (ctx == null) return;
    Scrollable.ensureVisible(
      ctx,
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
      alignment: 0.4,
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Container(
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: c.hairline)),
      ),
      child: SingleChildScrollView(
        controller: _controller,
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Gap.page - 8),
        child: Row(
          children: [
            for (var i = 0; i < widget.labels.length; i++)
              _RailItem(
                key: _keys[i] ??= GlobalKey(),
                label: widget.labels[i],
                selected: i == widget.index,
                onTap: () {
                  HapticFeedback.selectionClick();
                  widget.onChanged(i);
                },
              ),
          ],
        ),
      ),
    );
  }
}

class _RailItem extends StatelessWidget {
  const _RailItem({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return InkWell(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 13),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: selected ? c.accent : Colors.transparent,
              width: 2,
            ),
          ),
        ),
        child: Text(
          label.toUpperCase(),
          style: NewsType.eyebrow.copyWith(
            color: selected ? c.textPrimary : c.textTertiary,
            fontSize: 11,
          ),
        ),
      ),
    );
  }
}

/// The masthead: wordmark, dateline, optional action, and the house-style
/// info button - which is why this is a ConsumerWidget. Every screen renders a
/// masthead, so mounting the credit here is what makes it reachable from
/// everywhere without repeating it four times.
class Masthead extends ConsumerWidget {
  const Masthead({
    super.key,
    required this.dateline,
    this.trailing,
    this.subtitle,
  });

  final String dateline;
  final Widget? trailing;
  final String? subtitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = NewsTheme.of(context);
    final config = ref.watch(configProvider).valueOrNull ?? AppConfig.fallback;
    return Padding(
      padding: const EdgeInsets.fromLTRB(Gap.page, Gap.md, Gap.page, Gap.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Text('NEWS', style: NewsType.masthead.copyWith(color: c.textPrimary)),
                  Text('FIN', style: NewsType.masthead.copyWith(color: c.accent)),
                ],
              ),
              const SizedBox(height: 5),
              Text(
                subtitle ?? dateline,
                style: NewsType.meta.copyWith(color: c.textTertiary),
              ),
            ],
          ),
          const Spacer(),
          if (trailing != null) ...[trailing!, const SizedBox(width: Gap.sm)],
          AboutButton(sourceCount: config.sourceCount),
        ],
      ),
    );
  }
}

/// Switches one list between impact order and newest-first.
///
/// A pair of underlined labels rather than a pill toggle: it is the same kind
/// of control as the section rail it sits beside, and it keeps the header from
/// collecting a second visual language.
class LaneSwitch extends StatelessWidget {
  const LaneSwitch({super.key, required this.sort, required this.onChanged});

  final FeedSort sort;
  final ValueChanged<FeedSort> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final lane in FeedSort.values)
          Semantics(
            button: true,
            selected: lane == sort,
            label: lane == FeedSort.top
                ? 'Sort by impact'
                : 'Sort by most recent',
            child: InkWell(
              onTap: () {
                if (lane == sort) return;
                HapticFeedback.selectionClick();
                onChanged(lane);
              },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 8),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: lane == sort ? c.accent : Colors.transparent,
                      width: 2,
                    ),
                  ),
                ),
                child: Text(
                  lane.label.toUpperCase(),
                  style: NewsType.eyebrow.copyWith(
                    fontSize: 10,
                    color: lane == sort ? c.textPrimary : c.textTertiary,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Placeholder rows shown on a cold start.
///
/// Static blocks, not a shimmer sweep. A looping animation on every launch
/// reads as flicker, and the whole point of the cache is that this is rarely
/// on screen for more than a moment.
class HeadlineSkeleton extends StatelessWidget {
  const HeadlineSkeleton({super.key, this.rows = 7});

  final int rows;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    Widget bar(double widthFactor, double height) => FractionallySizedBox(
          alignment: Alignment.centerLeft,
          widthFactor: widthFactor,
          child: Container(
            height: height,
            decoration: BoxDecoration(
              color: c.surfaceRaised,
              borderRadius: BorderRadius.circular(3),
            ),
          ),
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(Gap.page, Gap.lg, Gap.page, Gap.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              bar(0.35, 10),
              const SizedBox(height: Gap.lg),
              bar(1.0, 26),
              const SizedBox(height: Gap.sm),
              bar(0.75, 26),
              const SizedBox(height: Gap.lg),
              bar(0.4, 10),
            ],
          ),
        ),
        for (var i = 0; i < rows; i++) ...[
          Container(height: 1, margin: const EdgeInsets.symmetric(horizontal: Gap.page), color: c.hairline),
          Padding(
            padding: const EdgeInsets.fromLTRB(Gap.page, Gap.lg, Gap.page, Gap.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                bar(i.isEven ? 0.95 : 0.8, 16),
                const SizedBox(height: Gap.sm),
                bar(i.isEven ? 0.6 : 0.72, 16),
                const SizedBox(height: Gap.md),
                bar(0.3, 9),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

/// Empty and error states. Plain language, one action, no illustration.
class NoticePanel extends StatelessWidget {
  const NoticePanel({
    super.key,
    required this.title,
    required this.body,
    this.actionLabel,
    this.onAction,
    this.icon,
  });

  final String title;
  final String body;
  final String? actionLabel;
  final VoidCallback? onAction;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(Gap.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 30, color: c.textTertiary),
              const SizedBox(height: Gap.lg),
            ],
            Text(
              title,
              textAlign: TextAlign.center,
              style: NewsType.headlineSmall.copyWith(color: c.textPrimary),
            ),
            const SizedBox(height: Gap.sm),
            Text(
              body,
              textAlign: TextAlign.center,
              style: NewsType.meta.copyWith(color: c.textSecondary, height: 1.5),
            ),
            if (actionLabel != null) ...[
              const SizedBox(height: Gap.xl),
              TextButton(
                onPressed: onAction,
                style: TextButton.styleFrom(
                  foregroundColor: c.accent,
                  backgroundColor: c.surfaceRaised,
                  padding: const EdgeInsets.symmetric(horizontal: Gap.xl, vertical: Gap.md),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                    side: BorderSide(color: c.hairline),
                  ),
                ),
                child: Text(actionLabel!, style: NewsType.button),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Thin banner shown when the list is stale or offline. Never blocks content.
class StaleBanner extends StatelessWidget {
  const StaleBanner({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Container(
      width: double.infinity,
      color: c.surfaceRaised,
      padding: const EdgeInsets.symmetric(horizontal: Gap.page, vertical: Gap.sm),
      child: Row(
        children: [
          Icon(Icons.cloud_off_rounded, size: 13, color: c.textTertiary),
          const SizedBox(width: Gap.sm),
          Expanded(
            child: Text(
              message,
              style: NewsType.meta.copyWith(color: c.textSecondary),
            ),
          ),
          if (onRetry != null)
            GestureDetector(
              onTap: onRetry,
              child: Text(
                'RETRY',
                style: NewsType.eyebrow.copyWith(color: c.accent, fontSize: 10),
              ),
            ),
        ],
      ),
    );
  }
}
