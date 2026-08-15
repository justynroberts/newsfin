/* MIT License - Copyright (c) fintonlabs.com */

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Design language.
///
/// Archetype: Editorial (see DESIGN.md). The reference points are the apps
/// people actually read the news in - the NYT, the FT, the Guardian, Apple
/// News. What they share is not a colour scheme, it is a typographic
/// hierarchy: one face worked hard across a dramatic size range, hairline
/// rules instead of cards, and colour used almost nowhere so that when it does
/// appear it means something.
///
/// Cards are deliberately absent. Stacked cards with shadows read as a social
/// feed; hairline-separated text blocks read as a front page.

class NewsColors {
  const NewsColors({
    required this.canvas,
    required this.surface,
    required this.surfaceRaised,
    required this.hairline,
    required this.hairlineStrong,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.accent,
    required this.accentMuted,
    required this.urgentHigh,
    required this.urgentMid,
    required this.urgentLow,
    required this.scrim,
  });

  final Color canvas;
  final Color surface;
  final Color surfaceRaised;
  final Color hairline;
  final Color hairlineStrong;
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color accent;
  final Color accentMuted;
  final Color urgentHigh;
  final Color urgentMid;
  final Color urgentLow;
  final Color scrim;

  /// Near-black rather than pure black: pure #000 crushes the hairlines that
  /// carry the whole layout, and makes large display type look thin.
  static const dark = NewsColors(
    canvas: Color(0xFF0A0A0C),
    surface: Color(0xFF121215),
    surfaceRaised: Color(0xFF19191E),
    hairline: Color(0xFF222228),
    hairlineStrong: Color(0xFF32323A),
    // Warm off-white. Pure white on near-black glares at 6am.
    textPrimary: Color(0xFFF4F3F0),
    textSecondary: Color(0xFF9C9CA6),
    textTertiary: Color(0xFF6A6A75),
    accent: Color(0xFF00C46A),
    accentMuted: Color(0xFF0C5537),
    urgentHigh: Color(0xFFFF453A),
    urgentMid: Color(0xFFFF9F0A),
    urgentLow: Color(0xFFB0AFB8),
    scrim: Color(0xCC000000),
  );

  /// Paper, not white - a warm neutral, the way newsprint and the FT read.
  static const light = NewsColors(
    canvas: Color(0xFFFBFAF7),
    surface: Color(0xFFFFFFFF),
    surfaceRaised: Color(0xFFF3F2ED),
    hairline: Color(0xFFE3E1DA),
    hairlineStrong: Color(0xFFC9C7BE),
    textPrimary: Color(0xFF14141A),
    textSecondary: Color(0xFF5C5C66),
    textTertiary: Color(0xFF8A8A94),
    accent: Color(0xFF00915A),
    accentMuted: Color(0xFFD3F0E0),
    urgentHigh: Color(0xFFD01A10),
    urgentMid: Color(0xFFB86A00),
    urgentLow: Color(0xFF7A7A84),
    scrim: Color(0x99000000),
  );
}

/// Impact expressed the way a newsroom would: not a number on a badge, but
/// how loud the story is allowed to be.
enum ImpactTier { lead, major, notable, routine }

/// Thresholds are calibrated against real score distributions: a typical poll
/// puts most stories in the 55-75 band, so a 65 cutoff painted half the list.
/// Scarcity is what makes the marker mean anything.
ImpactTier tierFor(double impact) {
  if (impact >= 82) return ImpactTier.lead;
  if (impact >= 73) return ImpactTier.major;
  if (impact >= 60) return ImpactTier.notable;
  return ImpactTier.routine;
}

Color tierColor(ImpactTier tier, NewsColors c) => switch (tier) {
      ImpactTier.lead => c.urgentHigh,
      ImpactTier.major => c.urgentMid,
      ImpactTier.notable => c.accent,
      ImpactTier.routine => c.urgentLow,
    };

class NewsType {
  /// One family, worked hard. Bricolage Grotesque is variable across optical
  /// size, width and weight, so hierarchy comes from the axes rather than from
  /// introducing a second typeface - which is what keeps an editorial layout
  /// coherent at six different sizes on one screen.
  static const display = 'Bricolage';
  static const sans = 'Bricolage';
  static const mono = 'SplineSansMono';

  /// The masthead. Tight tracking, heavy weight - a wordmark, not a title.
  static const masthead = TextStyle(
    fontFamily: display,
    fontSize: 23,
    fontWeight: FontWeight.w800,
    letterSpacing: -1.2,
    height: 1.0,
  );

  /// Section eyebrow: WORLD, UK, BUSINESS. Small caps, wide tracking.
  static const eyebrow = TextStyle(
    fontFamily: sans,
    fontSize: 10.5,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.4,
    height: 1.0,
  );

  /// The lead story of a section. Optical size and negative tracking matter
  /// enormously at this size - it is the difference between a headline and
  /// large body text.
  static const lead = TextStyle(
    fontFamily: display,
    fontSize: 31,
    fontWeight: FontWeight.w800,
    height: 1.06,
    letterSpacing: -1.1,
  );

  static const headline = TextStyle(
    fontFamily: display,
    fontSize: 19,
    fontWeight: FontWeight.w700,
    height: 1.2,
    letterSpacing: -0.5,
  );

  static const headlineSmall = TextStyle(
    fontFamily: display,
    fontSize: 16.5,
    fontWeight: FontWeight.w600,
    height: 1.26,
    letterSpacing: -0.35,
  );

  /// Standfirst / alternate framing of the same story. Dropping to 400 and
  /// opening the leading is what separates it from the headline above it.
  static const standfirst = TextStyle(
    fontFamily: display,
    fontSize: 15,
    fontWeight: FontWeight.w400,
    height: 1.45,
    letterSpacing: -0.1,
  );

  static const meta = TextStyle(
    fontFamily: sans,
    fontSize: 11.5,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.1,
    height: 1.0,
  );

  static const metaStrong = TextStyle(
    fontFamily: sans,
    fontSize: 11.5,
    fontWeight: FontWeight.w700,
    letterSpacing: 0.1,
    height: 1.0,
  );

  static const numeric = TextStyle(
    fontFamily: mono,
    fontSize: 11,
    fontWeight: FontWeight.w500,
    letterSpacing: -0.2,
    height: 1.0,
  );

  static const button = TextStyle(
    fontFamily: sans,
    fontSize: 13.5,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
  );
}

/// Spacing scale. A single rhythm keeps the page from looking assembled.
class Gap {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 22.0;
  static const xxl = 32.0;

  /// Horizontal page margin. Generous - whitespace is what separates an
  /// editorial layout from a dense feed.
  static const page = 20.0;
}

class NewsTheme extends InheritedWidget {
  const NewsTheme({super.key, required this.colors, required super.child});

  final NewsColors colors;

  static NewsColors of(BuildContext context) {
    final t = context.dependOnInheritedWidgetOfExactType<NewsTheme>();
    return t?.colors ?? NewsColors.dark;
  }

  @override
  bool updateShouldNotify(NewsTheme oldWidget) => oldWidget.colors != colors;
}

ThemeData buildTheme(NewsColors c, Brightness brightness) {
  return ThemeData(
    brightness: brightness,
    scaffoldBackgroundColor: c.canvas,
    canvasColor: c.canvas,
    splashFactory: InkSparkle.splashFactory,
    colorScheme: ColorScheme(
      brightness: brightness,
      primary: c.accent,
      onPrimary: brightness == Brightness.dark ? const Color(0xFF04150C) : Colors.white,
      secondary: c.accent,
      onSecondary: c.textPrimary,
      surface: c.surface,
      onSurface: c.textPrimary,
      error: c.urgentHigh,
      onError: Colors.white,
    ),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: c.accent,
      selectionColor: c.accent.withValues(alpha: 0.28),
    ),
    dividerColor: c.hairline,
    fontFamily: NewsType.sans,
  );
}

SystemUiOverlayStyle overlayFor(Brightness brightness) => SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness:
          brightness == Brightness.dark ? Brightness.light : Brightness.dark,
      statusBarBrightness: brightness,
      systemNavigationBarColor:
          brightness == Brightness.dark ? NewsColors.dark.canvas : NewsColors.light.canvas,
      systemNavigationBarIconBrightness:
          brightness == Brightness.dark ? Brightness.light : Brightness.dark,
    );
