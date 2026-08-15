/* MIT License - Copyright (c) fintonlabs.com */

import 'package:flutter/material.dart';

/// Motion.
///
/// The signature gesture is **rise-and-fade**: content arrives from 12px below
/// at zero opacity and settles. It recurs on story rows, on section changes and
/// on the coverage sheet, which is what makes the app feel authored rather than
/// assembled.
///
/// Motion here is strictly transitional. Nothing loops: a persistent control
/// that pulses forever reads as a rendering fault, not as information.
class Motion {
  /// Fast enough that a scroll never waits on it.
  static const quick = Duration(milliseconds: 140);
  static const normal = Duration(milliseconds: 260);
  static const slow = Duration(milliseconds: 420);

  /// Delay between siblings in a cascade. Above ~70ms a long list visibly
  /// crawls in; below ~30ms the stagger stops reading as deliberate.
  static const stagger = Duration(milliseconds: 45);

  /// Decelerating, no overshoot. Bouncy easing on text is fidgety.
  static const curve = Curves.easeOutCubic;
  static const emphasised = Cubic(0.2, 0, 0, 1);

  /// Honour the platform accessibility setting. Every animation in the app
  /// routes through here rather than checking the flag independently.
  static bool reduced(BuildContext context) =>
      MediaQuery.maybeDisableAnimationsOf(context) ?? false;
}

/// Rise-and-fade entrance, optionally staggered by position in a list.
///
/// Plays once on mount. It deliberately does not replay on rebuild - a row
/// that re-animates every time the feed refreshes is a distraction, not a
/// flourish.
class RiseIn extends StatefulWidget {
  const RiseIn({
    super.key,
    required this.child,
    this.index = 0,
    this.offset = 12,
    this.duration = Motion.normal,
    this.maxStaggered = 12,
  });

  final Widget child;
  final int index;
  final double offset;
  final Duration duration;

  /// Rows past this point appear immediately. A reader who scrolls fast should
  /// never be waiting on the fortieth item's turn in the queue.
  final int maxStaggered;

  @override
  State<RiseIn> createState() => _RiseInState();
}

class _RiseInState extends State<RiseIn> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: widget.duration,
  );

  late final Animation<double> _curved =
      CurvedAnimation(parent: _controller, curve: Motion.curve);

  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;

    if (Motion.reduced(context)) {
      _controller.value = 1;
      return;
    }
    final delay = Motion.stagger * widget.index.clamp(0, widget.maxStaggered);
    if (delay == Duration.zero) {
      _controller.forward();
    } else {
      Future.delayed(delay, () {
        if (mounted) _controller.forward();
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _curved,
      builder: (context, child) => Opacity(
        opacity: _curved.value,
        child: Transform.translate(
          offset: Offset(0, widget.offset * (1 - _curved.value)),
          child: child,
        ),
      ),
      child: widget.child,
    );
  }
}

/// Press feedback for tappable rows.
///
/// A headline is a large target, so an ink splash alone is weak feedback -
/// scaling the whole row a little confirms the tap on any size of element.
class PressFade extends StatefulWidget {
  const PressFade({
    super.key,
    required this.child,
    required this.onTap,
    this.onLongPress,
    this.scale = 0.985,
  });

  final Widget child;
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  final double scale;

  @override
  State<PressFade> createState() => _PressFadeState();
}

class _PressFadeState extends State<PressFade> {
  bool _down = false;

  void _set(bool value) {
    if (_down != value && mounted) setState(() => _down = value);
  }

  @override
  Widget build(BuildContext context) {
    final reduced = Motion.reduced(context);
    return GestureDetector(
      onTap: widget.onTap,
      onLongPress: widget.onLongPress,
      onTapDown: (_) => _set(true),
      onTapUp: (_) => _set(false),
      onTapCancel: () => _set(false),
      behavior: HitTestBehavior.opaque,
      child: AnimatedScale(
        scale: _down && !reduced ? widget.scale : 1.0,
        duration: Motion.quick,
        curve: Motion.curve,
        child: AnimatedOpacity(
          opacity: _down ? 0.62 : 1.0,
          duration: Motion.quick,
          child: widget.child,
        ),
      ),
    );
  }
}

/// Cross-fade used when a section's content is replaced wholesale.
class SectionSwap extends StatelessWidget {
  const SectionSwap({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: Motion.normal,
      switchInCurve: Motion.curve,
      switchOutCurve: Motion.curve,
      transitionBuilder: (child, animation) => FadeTransition(
        opacity: animation,
        child: SlideTransition(
          position: Tween(begin: const Offset(0, 0.02), end: Offset.zero)
              .animate(animation),
          child: child,
        ),
      ),
      child: child,
    );
  }
}
