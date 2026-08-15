import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/chrome.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = NewsTheme.of(context);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);
    final config = ref.watch(configProvider).valueOrNull ?? AppConfig.fallback;

    return SafeArea(
      bottom: false,
      child: ListView(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).padding.bottom + Gap.xxl * 2,
        ),
        children: [
          const Masthead(
            dateline: 'Settings',
            subtitle: 'Tune what reaches the top',
          ),
          Container(height: 1, color: c.hairline),

          _SectionHeader(
            title: 'YOUR MIX',
            note: 'How strongly each region pulls a story towards the top of '
                'Headlines. Set one to zero to hide it entirely.',
          ),
          for (final region in config.regions)
            _WeightRow(
              label: region.key == 'local'
                  ? 'Local (${config.locales.where((l) => l.key == settings.locale).map((l) => l.label).firstOrNull ?? 'choose area'})'
                  : region.label,
              value: settings.weights[region.key] ?? 1.0,
              onChanged: (v) => controller.setWeight(region.key, v),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(Gap.page, Gap.sm, Gap.page, Gap.lg),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: controller.resetWeights,
                style: TextButton.styleFrom(
                  foregroundColor: c.textSecondary,
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(0, 32),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Text('RESET TO DEFAULTS',
                    style: NewsType.eyebrow.copyWith(color: c.textSecondary)),
              ),
            ),
          ),

          _SectionHeader(
            title: 'LOCAL AREA',
            note: 'Which part of the UK the Local section covers.',
          ),
          _LocalePicker(
            locales: config.locales,
            selected: settings.locale,
            onChanged: controller.setLocale,
          ),

          _SectionHeader(
            title: 'WHAT COUNTS AS NEWS',
            note: 'A story is ranked partly on how many independent newsrooms '
                'ran it. Raise the minimum to filter out single-source chatter.',
          ),
          _ChoiceRow(
            label: 'Minimum sources',
            options: const {1: 'Any', 2: '2+', 3: '3+', 5: '5+'},
            value: settings.minSources,
            onChanged: controller.setMinSources,
          ),
          _ChoiceRow(
            label: 'Time window',
            options: const {12: '12h', 24: '24h', 48: '48h', 96: '4 days'},
            value: settings.hours,
            onChanged: controller.setHours,
          ),

          _SectionHeader(title: 'READING'),
          _ChoiceRow<ThemeMode>(
            label: 'Appearance',
            options: const {
              ThemeMode.dark: 'Dark',
              ThemeMode.light: 'Paper',
              ThemeMode.system: 'Auto',
            },
            value: settings.themeMode,
            onChanged: controller.setThemeMode,
          ),
          // Keys are ints (percent) because a const map cannot key on double.
          _ChoiceRow<int>(
            label: 'Text size',
            options: const {90: 'S', 100: 'M', 115: 'L', 130: 'XL'},
            value: (settings.textScale * 100).round(),
            onChanged: (pct) => controller.setTextScale(pct / 100),
          ),
          _SwitchRow(
            label: 'Open articles in app',
            note: 'Uses the in-app reader instead of leaving for the browser.',
            value: settings.openInApp,
            onChanged: controller.setOpenInApp,
          ),

          _SectionHeader(title: 'ABOUT'),
          _AboutBlock(sourceCount: config.sourceCount),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.note});

  final String title;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(Gap.page, Gap.xxl, Gap.page, Gap.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(title, style: NewsType.eyebrow.copyWith(color: c.accent)),
              const SizedBox(width: Gap.md),
              Expanded(child: Container(height: 1, color: c.hairline)),
            ],
          ),
          if (note != null) ...[
            const SizedBox(height: Gap.md),
            Text(
              note!,
              style: NewsType.meta.copyWith(color: c.textTertiary, height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}

/// Region weighting. Discrete stops rather than a continuous slider - "a bit
/// more Europe" is not a meaningful instruction, but "off / low / normal /
/// high" is.
class _WeightRow extends StatelessWidget {
  const _WeightRow({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final double value;
  final ValueChanged<double> onChanged;

  static const _stops = [0.0, 0.75, 1.5, 2.25, 3.0];
  static const _names = ['Off', 'Low', 'Normal', 'High', 'Top'];

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    var nearest = 0;
    for (var i = 1; i < _stops.length; i++) {
      if ((_stops[i] - value).abs() < (_stops[nearest] - value).abs()) nearest = i;
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(Gap.page, Gap.sm, Gap.page, Gap.sm),
      child: Row(
        children: [
          SizedBox(
            width: 118,
            child: Text(
              label,
              style: NewsType.headlineSmall.copyWith(
                color: nearest == 0 ? c.textTertiary : c.textPrimary,
                fontSize: 15,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Expanded(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                for (var i = 0; i < _stops.length; i++)
                  GestureDetector(
                    onTap: () {
                      HapticFeedback.selectionClick();
                      onChanged(_stops[i]);
                    },
                    child: Container(
                      margin: const EdgeInsets.only(left: 4),
                      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
                      decoration: BoxDecoration(
                        color: i == nearest
                            ? (i == 0 ? c.surfaceRaised : c.accent)
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: i == nearest
                              ? (i == 0 ? c.hairlineStrong : c.accent)
                              : c.hairline,
                        ),
                      ),
                      child: Text(
                        _names[i],
                        style: NewsType.meta.copyWith(
                          fontSize: 10.5,
                          color: i == nearest
                              ? (i == 0 ? c.textSecondary : c.canvas)
                              : c.textTertiary,
                          fontWeight: i == nearest ? FontWeight.w700 : FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ChoiceRow<T> extends StatelessWidget {
  const _ChoiceRow({
    required this.label,
    required this.options,
    required this.value,
    required this.onChanged,
  });

  final String label;
  final Map<T, String> options;
  final T value;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(Gap.page, Gap.sm, Gap.page, Gap.sm),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: NewsType.headlineSmall.copyWith(color: c.textPrimary, fontSize: 15),
            ),
          ),
          for (final entry in options.entries)
            GestureDetector(
              onTap: () {
                HapticFeedback.selectionClick();
                onChanged(entry.key);
              },
              child: Container(
                margin: const EdgeInsets.only(left: 4),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                decoration: BoxDecoration(
                  color: entry.key == value ? c.textPrimary : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: entry.key == value ? c.textPrimary : c.hairline,
                  ),
                ),
                child: Text(
                  entry.value,
                  style: NewsType.meta.copyWith(
                    fontSize: 10.5,
                    color: entry.key == value ? c.canvas : c.textTertiary,
                    fontWeight: entry.key == value ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.label,
    required this.value,
    required this.onChanged,
    this.note,
  });

  final String label;
  final String? note;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(Gap.page, Gap.sm, Gap.page, Gap.sm),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: NewsType.headlineSmall.copyWith(color: c.textPrimary, fontSize: 15),
                ),
                if (note != null) ...[
                  const SizedBox(height: 3),
                  Text(note!, style: NewsType.meta.copyWith(color: c.textTertiary)),
                ],
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            thumbColor: WidgetStatePropertyAll(value ? c.canvas : c.textTertiary),
            activeTrackColor: c.accent,
            inactiveTrackColor: c.surfaceRaised,
          ),
        ],
      ),
    );
  }
}

class _LocalePicker extends StatelessWidget {
  const _LocalePicker({
    required this.locales,
    required this.selected,
    required this.onChanged,
  });

  final List<Section> locales;
  final String selected;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    if (locales.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: Gap.page),
        child: Text('Loading areas...',
            style: NewsType.meta.copyWith(color: c.textTertiary)),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Gap.page),
      child: Wrap(
        spacing: 6,
        runSpacing: 6,
        children: [
          for (final l in locales)
            GestureDetector(
              onTap: () {
                HapticFeedback.selectionClick();
                onChanged(l.key);
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
                decoration: BoxDecoration(
                  color: l.key == selected ? c.accent : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: l.key == selected ? c.accent : c.hairline,
                  ),
                ),
                child: Text(
                  l.label,
                  style: NewsType.meta.copyWith(
                    color: l.key == selected ? c.canvas : c.textSecondary,
                    fontWeight: l.key == selected ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _AboutBlock extends StatelessWidget {
  const _AboutBlock({required this.sourceCount});

  final int sourceCount;

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Gap.page),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'NewsFin reads ${sourceCount > 0 ? sourceCount : 'over 200'} feeds from '
            'newsrooms across the UK, Ireland, Europe, the US and the rest of '
            'the world, groups the ones covering the same event, and ranks '
            'them by how much they matter.',
            style: NewsType.standfirst.copyWith(color: c.textSecondary, fontSize: 14),
          ),
          const SizedBox(height: Gap.lg),
          Text(
            'Ranking weighs how many independent newsrooms ran the story, how '
            'authoritative they are, how recent it is, how fast coverage is '
            'building, and the severity of what is being reported.',
            style: NewsType.standfirst.copyWith(color: c.textTertiary, fontSize: 13.5),
          ),
          const SizedBox(height: Gap.xl),
          Text('VERSION 1.0.0',
              style: NewsType.eyebrow.copyWith(color: c.textTertiary, fontSize: 9.5)),
        ],
      ),
    );
  }
}
