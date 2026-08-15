#!/usr/bin/env python3
"""Build the app-icon sources from the original artwork.

    python3 tools/make_icons.py && dart run flutter_launcher_icons

The artwork arrives as small flat black line work (~224px). Naively upscaling
it to 1024 leaves soft, grey edges, so this resamples high and then steepens
the edge ramp: the result keeps antialiasing but reads as crisp ink.

Three compositions come out, because the platforms crop differently:

    icon.png             full bleed, 82% content - iOS rounds the corners and
                         Android's legacy launcher may circle-crop it
    icon_foreground.png  transparent, 70% content - Android adaptive icons crop
                         to an inner safe zone and parallax over it, and the
                         generator adds another 16% inset on top
    icon_maskable.png    58% content - the web maskable safe zone is a circle

Run from the `app/` directory.
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
ICON_DIR = HERE / "assets" / "icon"
SOURCE = ICON_DIR / "source.png"

# The app's own palette, so the icon belongs to the product it opens: paper is
# the light theme's canvas, ink its text colour.
PAPER = (0xFB, 0xFA, 0xF7)
INK = (0x14, 0x14, 0x1A)

MASTER = 2048
INK_THRESHOLD = 0.35
EDGE_GAIN = 6.0


def build_mask() -> Image.Image:
    """Tight, high-resolution alpha mask of the artwork."""
    im = Image.open(SOURCE).convert("RGBA")

    # Flatten onto white so a transparent background and a white background
    # are treated identically.
    flat = Image.new("RGB", im.size, "white")
    flat.paste(im, mask=im.split()[3])

    ink = 1.0 - np.asarray(flat.convert("L")).astype(np.float32) / 255.0
    ys, xs = np.where(ink > INK_THRESHOLD)
    if not len(xs):
        raise SystemExit(f"no artwork found in {SOURCE}")

    pad = 2
    box = (
        max(0, xs.min() - pad),
        max(0, ys.min() - pad),
        min(im.size[0], xs.max() + 1 + pad),
        min(im.size[1], ys.max() + 1 + pad),
    )
    mask = Image.fromarray((ink * 255).astype(np.uint8)).crop(box)

    # Square on the longer side so nothing distorts.
    w, h = mask.size
    side = max(w, h)
    square = Image.new("L", (side, side), 0)
    square.paste(mask, ((side - w) // 2, (side - h) // 2))

    up = square.resize((MASTER, MASTER), Image.LANCZOS)
    a = np.asarray(up).astype(np.float32) / 255.0
    a = np.clip((a - 0.5) * EDGE_GAIN + 0.5, 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))


def compose(mask: Image.Image, size: int, ratio: float, bg=None) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (*bg, 255) if bg else (0, 0, 0, 0))
    c = max(1, int(size * ratio))
    ink = Image.new("RGBA", (c, c), (*INK, 255))
    offset = (size - c) // 2
    canvas.paste(ink, (offset, offset), mask.resize((c, c), Image.LANCZOS))
    return canvas


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    mask = build_mask()

    compose(mask, 1024, 0.82, PAPER).convert("RGB").save(ICON_DIR / "icon.png")
    # 0.70, not the ~0.56 the safe zone alone suggests: flutter_launcher_icons
    # wraps this drawable in a further 16%-per-side inset, so the two compound.
    # At 0.56 the mark ended up filling barely half the launcher's circle.
    compose(mask, 1024, 0.70).save(ICON_DIR / "icon_foreground.png")
    compose(mask, 1024, 0.58, PAPER).convert("RGB").save(ICON_DIR / "icon_maskable.png")

    # flutter_launcher_icons derives the web maskable icons from the full-bleed
    # art, which a circular mask clips through the ears, and writes a 16px
    # favicon that turns this artwork to mush. Both are corrected here, so run
    # this again after the generator if you re-run it.
    web = HERE / "web"
    if web.is_dir():
        maskable = Image.open(ICON_DIR / "icon_maskable.png").convert("RGB")
        for size in (192, 512):
            maskable.resize((size, size), Image.LANCZOS).save(
                web / "icons" / f"Icon-maskable-{size}.png"
            )
        Image.open(ICON_DIR / "icon.png").convert("RGB").resize(
            (64, 64), Image.LANCZOS
        ).save(web / "favicon.png")

        # The generator also rewrites the PWA splash colour to the icon's paper
        # background. The app opens dark, so that shows a white flash before
        # the first frame - put it back.
        manifest = web / "manifest.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text())
            data["background_color"] = "#0A0A0C"
            data["theme_color"] = "#0A0A0C"
            manifest.write_text(json.dumps(data, indent=2) + "\n")

    print("icon sources written to", ICON_DIR)


if __name__ == "__main__":
    main()
