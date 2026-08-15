# NewsFin — design record

Written per the `house-style` skill so a later session can see what was already
used here and pick differently next time.

## Archetype: **Editorial**

Wide measure, big type scale, rules instead of cards.

Chosen because the four most recent sibling projects all landed in the same
register — `mpcee` (Raycast-inspired: dark, pill radii, inset shadows),
`steprail` (Linear-inspired: achromatic + indigo, 6px radius, hairline
translucent borders), plus `alto` and `rapidresponse`. All are dark
SaaS-console surfaces built from cards with one accent hue. Editorial is a
genuinely different skeleton, and it is the right one for a news reader: a
front page is a typographic hierarchy, not a stack of cards.

**The single rule that defines it here: there are no cards.** Stories are
separated by inset hairlines. Stacked cards with shadows read as a social feed;
hairline-separated text blocks read as a newspaper.

## Axis picks

| Axis | Pick | Why |
|---|---|---|
| **Layout** | Single full-bleed column, asymmetric lead block | The lead story gets ~3× the height of a standard row. That variation is what stops 60 headlines reading as a wall. |
| **Type scale** | Dramatic (~1.55) — 31 / 19 / 16.5 / 15 / 11.5 / 10.5 | A flat scale makes every headline equally important, which is the opposite of what an impact-ranked app is claiming. |
| **Surface** | Flat fills, hairline rules, zero elevation | No shadows anywhere. Deliberately unlike `mpcee`'s inset shadows and `steprail`'s translucent borders. |
| **Radius** | Mixed by role: 0px structure, 6px controls, 14px dialogs | Structural elements (rules, rows, the lead block) are hard-edged; only things you press are rounded. |
| **Accent** | Near-monochrome + one signal colour, plus a *scarce* urgency scale | Green (`#00C46A` dark / `#00915A` light) for interaction. Amber and red appear **only** on stories scoring ≥73 and ≥82 — recalibrated after the first build painted half the list. |
| **Motion signature** | **Rise-and-fade**, 12px, staggered 45ms | Recurs on story rows, the lead block and the about dialog. One gesture, reused, so the app feels authored. |
| **Ground texture** | Plain | Any texture behind a dense type hierarchy fights the reading. |

## Typography

- **Display + primary — Bricolage Grotesque.** Variable across `opsz`, `wdth`
  and `wght`, so the entire hierarchy comes from one family: masthead at 800
  with −1.2 tracking, lead at 800/−1.1, headlines at 700/−0.5, standfirst
  dropping to 400 with open leading.
- **Mono slot — Spline Sans Mono.** Timestamps, source counts, impact scores.
  Every number in the app is monospaced, so digits do not jitter as a list
  refreshes.

An earlier build used Newsreader (a serif) for headlines. It looked good but
the house style makes Bricolage the primary face, so the serif was removed
rather than kept as a second family.

## Colour

Both themes are complete palettes, not one theme with overrides.

- **Dark** — canvas `#0A0A0C`, near-black rather than pure black so hairlines
  stay visible. Text is a warm off-white `#F4F3F0`; pure white on near-black
  glares at 6am, which is the hour this app is designed for.
- **Light ("Paper")** — canvas `#FBFAF7`, a warm neutral rather than white, the
  way newsprint and the FT read.

Three theme states: explicit Dark, explicit Paper, and Auto (follows system).

## Impact, expressed visually

The ranking is the product, so it has to be legible without a number:

1. **Position** — the list is ordered by it.
2. **Size** — the lead story is set at 31px.
3. **A margin rule** — a 2.5px vertical rule beside the headline, coloured by
   tier, and only for the top two tiers.
4. **"25 sources"** — the reader-facing form of the score. Self-evidently
   meaningful in a way "impact 92.8" is not; it turns red above 8 sources.

The numeric score appears in exactly one place: the coverage sheet. A list that
shows scores reads as a dashboard, not a front page.

## Accessibility

- Both palettes target WCAG AA; the light theme is the one that usually fails,
  so secondary text sits at `#5C5C66` on `#FBFAF7` rather than a lighter grey.
- `prefers-reduced-motion` is honoured through `Motion.reduced()` — every
  animation routes through one check rather than each widget testing the flag.
- Story rows carry semantic labels reading headline, source, age and source
  count, so the ranking is available to a screen reader.
- Reader-controlled text scale (S/M/L/XL) is clamped so the type grid survives
  an extreme system setting.
