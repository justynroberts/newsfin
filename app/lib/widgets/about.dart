/* MIT License - Copyright (c) fintonlabs.com */

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../motion.dart';
import '../theme.dart';
import 'chrome.dart';

/// The house-style info affordance, present on every screen.
///
/// Placed at the end of the masthead, which every tab renders, so it is always
/// one tap away without ever overlapping a primary control or the last row of
/// a scrolling list.
class AboutButton extends StatelessWidget {
  const AboutButton({super.key, this.sourceCount = 0});

  final int sourceCount;

  @override
  Widget build(BuildContext context) {
    return IconAction(
      icon: Icons.info_outline_rounded,
      label: 'About this app',
      onTap: () => AboutPanel.show(context, sourceCount),
    );
  }
}

class AboutPanel extends StatelessWidget {
  const AboutPanel({super.key, required this.sourceCount});

  final int sourceCount;

  static Future<void> show(BuildContext context, int sourceCount) {
    final c = NewsTheme.of(context);
    return showDialog(
      context: context,
      barrierColor: c.scrim,
      // Escape and barrier taps both dismiss; Flutter's dialog route gives
      // both for free, along with focus trapping.
      barrierDismissible: true,
      builder: (_) => NewsTheme(
        colors: c,
        child: AboutPanel(sourceCount: sourceCount),
      ),
    );
  }

  Future<void> _openSite(BuildContext context) async {
    final uri = Uri.parse('https://fintonlabs.com');
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open fintonlabs.com')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);

    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.all(Gap.xl),
      child: RiseIn(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 380),
          decoration: BoxDecoration(
            color: c.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: c.hairline),
          ),
          padding: const EdgeInsets.all(Gap.xl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text('NEWS', style: NewsType.masthead.copyWith(color: c.textPrimary)),
                  Text('FIN', style: NewsType.masthead.copyWith(color: c.accent)),
                  const Spacer(),
                  Semantics(
                    button: true,
                    label: 'Close',
                    child: InkWell(
                      onTap: () => Navigator.of(context).pop(),
                      borderRadius: BorderRadius.circular(16),
                      child: Padding(
                        padding: const EdgeInsets.all(4),
                        child: Icon(Icons.close_rounded, size: 19, color: c.textSecondary),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: Gap.lg),
              Text(
                'Impact-ranked world news. NewsFin reads '
                '${sourceCount > 0 ? '$sourceCount' : 'over 200'} feeds from newsrooms '
                'across the UK, Ireland, Europe, the US and the wider world, groups '
                'the ones covering the same event, and ranks them by how much they '
                'actually matter.',
                style: NewsType.standfirst.copyWith(color: c.textSecondary),
              ),
              const SizedBox(height: Gap.xl),
              Container(height: 1, color: c.hairline),
              const SizedBox(height: Gap.lg),
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('MADE BY',
                            style: NewsType.eyebrow.copyWith(
                                color: c.textTertiary, fontSize: 9.5)),
                        const SizedBox(height: 6),
                        Semantics(
                          link: true,
                          child: InkWell(
                            onTap: () => _openSite(context),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  'FintonLabs',
                                  style: NewsType.headlineSmall
                                      .copyWith(color: c.accent, fontSize: 17),
                                ),
                                const SizedBox(width: 4),
                                Icon(Icons.north_east_rounded,
                                    size: 13, color: c.accent),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('VERSION',
                          style: NewsType.eyebrow
                              .copyWith(color: c.textTertiary, fontSize: 9.5)),
                      const SizedBox(height: 6),
                      Text('1.0.0',
                          style: NewsType.numeric
                              .copyWith(color: c.textSecondary, fontSize: 13)),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
