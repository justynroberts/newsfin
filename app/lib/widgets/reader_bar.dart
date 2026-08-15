/* MIT License - Copyright (c) fintonlabs.com */

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models.dart';
import '../motion.dart';
import '../reader.dart';
import '../theme.dart';

/// Starts the spoken briefing.
///
/// Deliberately a wide, labelled control rather than a small icon: the people
/// who need it most are the people least able to hit a 24px target.
class ListenButton extends ConsumerWidget {
  const ListenButton({super.key, required this.stories});

  final List<Story> stories;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = NewsTheme.of(context);
    final reader = ref.watch(readerProvider);
    // Only hidden once speech has been tried and failed - never on a startup
    // probe, which cannot succeed before the user has interacted at all.
    if (!reader.available) return const SizedBox.shrink();
    // Nothing to read yet: offering the control would make the first tap do
    // nothing at all, which is worse than not offering it.
    if (stories.isEmpty && !reader.active) return const SizedBox.shrink();

    final playing = reader.playing;

    return Semantics(
      button: true,
      label: playing ? 'Pause reading headlines' : 'Listen to the headlines',
      child: Tooltip(
        message: playing ? 'Pause' : 'Listen to the headlines',
        child: InkWell(
          onTap: () {
            HapticFeedback.selectionClick();
            ref.read(readerProvider.notifier).toggle(stories);
          },
          borderRadius: BorderRadius.circular(8),
          child: Container(
            constraints: const BoxConstraints(minHeight: 40),
            padding: const EdgeInsets.symmetric(horizontal: Gap.md, vertical: Gap.sm),
            decoration: BoxDecoration(
              color: playing ? c.accent : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: playing ? c.accent : c.hairline),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  playing ? Icons.pause_rounded : Icons.headphones_rounded,
                  size: 15,
                  color: playing ? c.canvas : c.textSecondary,
                ),
                const SizedBox(width: 6),
                Text(
                  playing ? 'PAUSE' : 'LISTEN',
                  style: NewsType.eyebrow.copyWith(
                    color: playing ? c.canvas : c.textSecondary,
                    fontSize: 9.5,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Playback controls, shown above the navigation bar while a briefing runs.
///
/// Large targets, plain labels, and the headline currently being spoken shown
/// in full so a partially sighted reader can follow along or tap through to
/// the article.
class ReaderBar extends ConsumerWidget {
  const ReaderBar({super.key, required this.onOpen});

  final void Function(Story story) onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = NewsTheme.of(context);
    final reader = ref.watch(readerProvider);
    final controller = ref.read(readerProvider.notifier);

    if (!reader.active) return const SizedBox.shrink();

    final story = controller.currentStory;

    return RiseIn(
      offset: 20,
      child: Container(
        decoration: BoxDecoration(
          color: c.surfaceRaised,
          border: Border(top: BorderSide(color: c.hairlineStrong)),
        ),
        padding: const EdgeInsets.fromLTRB(Gap.page, Gap.md, Gap.page, Gap.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'READING ${reader.index + 1} OF ${reader.total}',
                  style: NewsType.eyebrow.copyWith(color: c.accent, fontSize: 9.5),
                ),
                const Spacer(),
                Semantics(
                  button: true,
                  label: 'Stop reading',
                  child: InkWell(
                    onTap: controller.stop,
                    borderRadius: BorderRadius.circular(6),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      child: Text(
                        'STOP',
                        style: NewsType.eyebrow
                            .copyWith(color: c.textSecondary, fontSize: 9.5),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: Gap.sm),
            // Tapping the headline opens the article being read.
            Semantics(
              button: true,
              label: 'Open the story being read',
              child: InkWell(
                onTap: story == null ? null : () => onOpen(story),
                child: Text(
                  reader.currentTitle,
                  style: NewsType.headlineSmall.copyWith(color: c.textPrimary),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            const SizedBox(height: Gap.md),
            Row(
              children: [
                _ReaderControl(
                  icon: Icons.skip_previous_rounded,
                  label: 'Previous headline',
                  onTap: controller.previous,
                ),
                const SizedBox(width: Gap.sm),
                _ReaderControl(
                  icon: reader.playing
                      ? Icons.pause_rounded
                      : Icons.play_arrow_rounded,
                  label: reader.playing ? 'Pause' : 'Resume',
                  primary: true,
                  onTap: () =>
                      reader.playing ? controller.pause() : controller.resume(),
                ),
                const SizedBox(width: Gap.sm),
                _ReaderControl(
                  icon: Icons.skip_next_rounded,
                  label: 'Next headline',
                  onTap: controller.next,
                ),
                const Spacer(),
                if (reader.error != null)
                  Flexible(
                    child: Text(
                      reader.error!,
                      style: NewsType.meta.copyWith(color: c.urgentMid),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 48px minimum, which is the accessibility floor for a touch target and the
/// whole point of this feature.
class _ReaderControl extends StatelessWidget {
  const _ReaderControl({
    required this.icon,
    required this.label,
    required this.onTap,
    this.primary = false,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Semantics(
      button: true,
      label: label,
      child: Tooltip(
        message: label,
        child: InkWell(
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          borderRadius: BorderRadius.circular(10),
          child: Container(
            width: primary ? 60 : 52,
            height: 48,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: primary ? c.accent : Colors.transparent,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: primary ? c.accent : c.hairlineStrong),
            ),
            child: Icon(
              icon,
              size: primary ? 26 : 22,
              color: primary ? c.canvas : c.textPrimary,
            ),
          ),
        ),
      ),
    );
  }
}
