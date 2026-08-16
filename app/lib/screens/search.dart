import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../state.dart';
import '../theme.dart';
import '../widgets/chrome.dart';
import '../widgets/coverage_sheet.dart';
import '../widgets/story_tile.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _controller = TextEditingController();
  final _focus = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  Future<void> _open(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    final mode = ref.read(settingsProvider).openInApp
        ? LaunchMode.inAppBrowserView
        : LaunchMode.externalApplication;
    try {
      await launchUrl(uri, mode: mode);
    } catch (_) {
      await launchUrl(uri, mode: LaunchMode.platformDefault);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = NewsTheme.of(context);
    final results = ref.watch(searchProvider);

    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          // Search had no masthead, so it was the one screen without the
          // About control - the house style asks for it everywhere.
          const Masthead(dateline: 'Search', subtitle: 'Across every source'),
          Padding(
            padding: const EdgeInsets.fromLTRB(Gap.page, 0, Gap.page, Gap.md),
            child: Container(
              decoration: BoxDecoration(
                color: c.surfaceRaised,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: c.hairline),
              ),
              padding: const EdgeInsets.symmetric(horizontal: Gap.md),
              child: Row(
                children: [
                  Icon(Icons.search_rounded, size: 18, color: c.textTertiary),
                  const SizedBox(width: Gap.sm),
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      focusNode: _focus,
                      autocorrect: false,
                      textInputAction: TextInputAction.search,
                      style: NewsType.headlineSmall.copyWith(
                        color: c.textPrimary,
                        fontFamily: NewsType.sans,
                        fontSize: 15,
                      ),
                      cursorColor: c.accent,
                      decoration: InputDecoration(
                        isDense: true,
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(vertical: 13),
                        hintText: 'Search every source',
                        hintStyle: NewsType.meta.copyWith(
                          color: c.textTertiary,
                          fontSize: 14,
                        ),
                      ),
                      onChanged: ref.read(searchProvider.notifier).query,
                    ),
                  ),
                  if (_controller.text.isNotEmpty)
                    GestureDetector(
                      onTap: () {
                        _controller.clear();
                        ref.read(searchProvider.notifier).query('');
                        setState(() {});
                      },
                      child: Icon(Icons.close_rounded, size: 17, color: c.textTertiary),
                    ),
                ],
              ),
            ),
          ),
          Container(height: 1, color: c.hairline),
          Expanded(
            child: results.when(
              loading: () => const HeadlineSkeleton(rows: 5),
              error: (e, _) => NoticePanel(
                icon: Icons.error_outline_rounded,
                title: 'Search failed',
                body: '$e',
              ),
              data: (stories) {
                if (_controller.text.trim().length < 2) {
                  return const NoticePanel(
                    icon: Icons.search_rounded,
                    title: 'Search the archive',
                    body: 'Find any story from the last few days across every '
                        'source, ranked by how widely it was covered.',
                  );
                }
                if (stories.isEmpty) {
                  return NoticePanel(
                    icon: Icons.search_off_rounded,
                    title: 'No matches',
                    body: 'Nothing in the last few days matches '
                        '"${_controller.text.trim()}".',
                  );
                }
                return ListView.separated(
                  itemCount: stories.length,
                  separatorBuilder: (_, __) => const StoryDivider(),
                  itemBuilder: (context, i) => StoryTile(
                    story: stories[i],
                    compact: true,
                    onTap: () => _open(stories[i].url),
                    onCoverage: () =>
                        CoverageSheet.show(context, stories[i], _open),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
