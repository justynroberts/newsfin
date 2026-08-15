import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';

/// Every outlet's version of one story.
///
/// No other mainstream news app shows you this, and it is the most useful
/// thing the clustering produces: the same event, headlined ten different
/// ways, so you can see the framing rather than just one outlet's choice.
class CoverageSheet extends StatelessWidget {
  const CoverageSheet({
    super.key,
    required this.story,
    required this.onOpen,
  });

  final Story story;
  final void Function(String url) onOpen;

  static Future<void> show(
    BuildContext context,
    Story story,
    void Function(String url) onOpen,
  ) {
    final c = NewsTheme.of(context);
    return showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      barrierColor: c.scrim,
      isScrollControlled: true,
      builder: (_) => NewsTheme(
        colors: c,
        child: CoverageSheet(story: story, onOpen: onOpen),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final tier = tierFor(story.impact);

    return DraggableScrollableSheet(
      initialChildSize: 0.72,
      minChildSize: 0.4,
      maxChildSize: 0.94,
      expand: false,
      builder: (context, controller) => Container(
        decoration: BoxDecoration(
          color: c.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
          border: Border(top: BorderSide(color: c.hairline)),
        ),
        child: Column(
          children: [
            // Grab handle
            Container(
              width: 36,
              height: 4,
              margin: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: c.hairlineStrong,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Expanded(
              child: ListView(
                controller: controller,
                padding: EdgeInsets.only(
                  bottom: MediaQuery.of(context).padding.bottom + Gap.xxl,
                ),
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(Gap.page, Gap.sm, Gap.page, 0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(width: 22, height: 2.5, color: tierColor(tier, c)),
                            const SizedBox(width: Gap.sm),
                            Text(
                              '${story.sources} SOURCES COVERING',
                              style: NewsType.eyebrow.copyWith(color: c.textSecondary),
                            ),
                          ],
                        ),
                        const SizedBox(height: Gap.lg),
                        Text(
                          story.title,
                          style: NewsType.headline.copyWith(
                            color: c.textPrimary,
                            fontSize: 22,
                          ),
                        ),
                        const SizedBox(height: Gap.md),
                        _ImpactBar(impact: story.impact),
                      ],
                    ),
                  ),
                  const SizedBox(height: Gap.xl),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: Gap.page),
                    child: Text(
                      'HOW IT IS BEING REPORTED',
                      style: NewsType.eyebrow.copyWith(color: c.textTertiary),
                    ),
                  ),
                  const SizedBox(height: Gap.md),
                  for (final item in story.coverage) _CoverageRow(item: item, onOpen: onOpen),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CoverageRow extends StatelessWidget {
  const _CoverageRow({required this.item, required this.onOpen});

  final Coverage item;
  final void Function(String url) onOpen;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return InkWell(
      onTap: () => onOpen(item.url),
      child: Container(
        padding: const EdgeInsets.fromLTRB(Gap.page, Gap.md, Gap.page, Gap.md),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: c.hairline)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  item.source.toUpperCase(),
                  style: NewsType.eyebrow.copyWith(color: c.accent, fontSize: 10),
                ),
                const Spacer(),
                Text(item.age, style: NewsType.numeric.copyWith(color: c.textTertiary)),
              ],
            ),
            const SizedBox(height: Gap.sm),
            Text(
              item.title,
              style: NewsType.headlineSmall.copyWith(color: c.textPrimary),
            ),
          ],
        ),
      ),
    );
  }
}

/// The numeric score, shown only here - deep enough in that a curious reader
/// finds it, never so prominent that the list looks like a dashboard.
class _ImpactBar extends StatelessWidget {
  const _ImpactBar({required this.impact});

  final double impact;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final tier = tierFor(impact);
    final label = switch (tier) {
      ImpactTier.lead => 'Leading the news',
      ImpactTier.major => 'Major story',
      ImpactTier.notable => 'Notable',
      ImpactTier.routine => 'Routine',
    };

    return Row(
      children: [
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: (impact / 100).clamp(0.0, 1.0),
              minHeight: 3,
              backgroundColor: c.hairline,
              valueColor: AlwaysStoppedAnimation(tierColor(tier, c)),
            ),
          ),
        ),
        const SizedBox(width: Gap.md),
        Text(label, style: NewsType.meta.copyWith(color: c.textSecondary)),
        const SizedBox(width: Gap.sm),
        Text(
          impact.toStringAsFixed(0),
          style: NewsType.numeric.copyWith(color: tierColor(tier, c)),
        ),
      ],
    );
  }
}
