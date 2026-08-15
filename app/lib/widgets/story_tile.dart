import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models.dart';
import '../theme.dart';

/// Metadata line: SOURCE · 4h · 12 sources
///
/// Every element is deliberately small and quiet. The headline is the only
/// thing competing for attention; everything else is there to be checked, not
/// read.
class StoryMeta extends StatelessWidget {
  const StoryMeta({
    super.key,
    required this.story,
    this.emphasise = false,
  });

  final Story story;
  final bool emphasise;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final tier = tierFor(story.impact);

    return DefaultTextStyle(
      style: NewsType.meta.copyWith(color: c.textTertiary),
      child: Row(
        children: [
          Flexible(
            child: Text(
              story.source.toUpperCase(),
              style: NewsType.eyebrow.copyWith(
                color: emphasise ? c.textSecondary : c.textTertiary,
                fontSize: 10,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          _dot(c),
          Text(story.age, style: NewsType.numeric.copyWith(color: c.textTertiary)),
          if (story.sources > 1) ...[
            _dot(c),
            // The corroboration count is the reader-facing form of the impact
            // score. "14 sources" is self-evidently meaningful in a way that
            // "impact 78.2" never is.
            Text(
              '${story.sources} sources',
              style: NewsType.numeric.copyWith(
                color: story.sources >= 8
                    ? tierColor(tier, c)
                    : c.textTertiary,
                fontWeight: story.sources >= 8 ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ],
          if (story.isFresh) ...[
            _dot(c),
            Text(
              'NEW',
              style: NewsType.eyebrow.copyWith(color: c.accent, fontSize: 9.5),
            ),
          ],
        ],
      ),
    );
  }

  Widget _dot(NewsColors c) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6),
        child: Text('·', style: TextStyle(color: c.hairlineStrong, height: 1)),
      );
}

/// The lead story of a section.
///
/// Modelled on how a front page opens: one story given real size, a second
/// outlet's framing beneath it as a standfirst, and a rule above it carrying
/// the section label. No image - by design. Headlines carry more information
/// per square centimetre than a stock photo of a building.
class LeadStory extends StatelessWidget {
  const LeadStory({
    super.key,
    required this.story,
    required this.onTap,
    required this.onCoverage,
    this.label,
  });

  final Story story;
  final VoidCallback onTap;
  final VoidCallback onCoverage;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final tier = tierFor(story.impact);

    return Semantics(
      button: true,
      label: '${story.title}. ${story.source}, ${story.age}, '
          '${story.sources} sources covering.',
      child: InkWell(
        onTap: onTap,
        onLongPress: story.coverage.length > 1 ? onCoverage : null,
        splashColor: c.accent.withValues(alpha: 0.06),
        highlightColor: c.surfaceRaised,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(Gap.page, Gap.lg, Gap.page, Gap.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (label != null) ...[
                Row(
                  children: [
                    Container(width: 22, height: 2.5, color: tierColor(tier, c)),
                    const SizedBox(width: Gap.sm),
                    Text(
                      label!.toUpperCase(),
                      style: NewsType.eyebrow.copyWith(color: c.textSecondary),
                    ),
                  ],
                ),
                const SizedBox(height: Gap.lg),
              ],
              Text(
                story.title,
                style: NewsType.lead.copyWith(color: c.textPrimary),
              ),
              if (story.altTitle.isNotEmpty) ...[
                const SizedBox(height: Gap.md),
                Text(
                  story.altTitle,
                  style: NewsType.standfirst.copyWith(color: c.textSecondary),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              const SizedBox(height: Gap.lg),
              StoryMeta(story: story, emphasise: true),
              if (story.coverage.length > 1) ...[
                const SizedBox(height: Gap.md),
                CoverageStrip(story: story, onTap: onCoverage),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A standard row.
///
/// The thin vertical rule on the left encodes impact by colour. It reads as a
/// margin rule on a printed page rather than as a badge, which keeps the list
/// calm while still ranking visibly.
class StoryTile extends StatelessWidget {
  const StoryTile({
    super.key,
    required this.story,
    required this.onTap,
    required this.onCoverage,
    this.rank,
    this.compact = false,
  });

  final Story story;
  final VoidCallback onTap;
  final VoidCallback onCoverage;
  final int? rank;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final tier = tierFor(story.impact);
    final showRule = tier == ImpactTier.lead || tier == ImpactTier.major;

    return Semantics(
      button: true,
      label: '${story.title}. ${story.source}, ${story.age}, '
          '${story.sources} sources covering.',
      child: InkWell(
        onTap: onTap,
        onLongPress: story.coverage.length > 1 ? onCoverage : null,
        splashColor: c.accent.withValues(alpha: 0.06),
        highlightColor: c.surfaceRaised,
        child: Padding(
          padding: EdgeInsets.fromLTRB(
            Gap.page,
            compact ? Gap.md : Gap.lg,
            Gap.page,
            compact ? Gap.md : Gap.lg,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (showRule)
                Container(
                  width: 2.5,
                  height: compact ? 30 : 38,
                  margin: const EdgeInsets.only(right: Gap.md, top: 3),
                  decoration: BoxDecoration(
                    color: tierColor(tier, c),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              if (rank != null)
                Padding(
                  padding: const EdgeInsets.only(right: Gap.md, top: 2),
                  child: SizedBox(
                    width: 20,
                    child: Text(
                      '$rank',
                      style: NewsType.numeric.copyWith(
                        color: c.textTertiary,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      story.title,
                      style: (compact ? NewsType.headlineSmall : NewsType.headline)
                          .copyWith(color: c.textPrimary),
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: Gap.sm + 2),
                    StoryMeta(story: story),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The outlets carrying a story, shown as a row of names.
///
/// This is the feature that justifies the whole clustering pipeline: seeing at
/// a glance that the BBC, Reuters, Le Monde and Al Jazeera are all running the
/// same thing tells you more about its importance than any score could.
class CoverageStrip extends StatelessWidget {
  const CoverageStrip({super.key, required this.story, required this.onTap});

  final Story story;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final names = story.coverage.map((e) => e.source).take(4).toList();
    final extra = story.sources - names.length;

    return InkWell(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      borderRadius: BorderRadius.circular(6),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: [
            Flexible(
              child: Text(
                names.join(' · '),
                style: NewsType.meta.copyWith(color: c.textSecondary),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (extra > 0)
              Text(
                '  +$extra',
                style: NewsType.numeric.copyWith(color: c.accent),
              ),
            const SizedBox(width: Gap.xs),
            Icon(Icons.chevron_right_rounded, size: 15, color: c.textTertiary),
          ],
        ),
      ),
    );
  }
}

/// Hairline divider. Inset from the page margin the way a broadsheet rules
/// between items - a full-bleed line reads as a hard section break.
class StoryDivider extends StatelessWidget {
  const StoryDivider({super.key, this.inset = true});

  final bool inset;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Container(
      height: 1,
      margin: EdgeInsets.symmetric(horizontal: inset ? Gap.page : 0),
      color: c.hairline,
    );
  }
}
