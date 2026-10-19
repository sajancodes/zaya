"""Generate the Android companion's character art from the desktop assets.

The phone shows the SAME Zaya: no new art is drawn here, the existing desktop
images are cropped chest-up and resized. Two rules keep it honest:

  * one crop window for every emotion, taken from the union of the images'
    opaque bounds, so Zaya does not jump between expressions on the phone;
  * a missing emotion falls back exactly like the desktop does
    (emotion → neutral → standby), never to an invented asset.

Run:  .venv\\Scripts\\python.exe tools/make_android_assets.py
Outputs (all overwritten, all deterministic):
    mobile/android/app/src/main/res/drawable-nodpi/zaya_<state>.png
    mobile/android/app/src/main/res/drawable-nodpi/ic_launcher_foreground.png
    mobile/android/app/src/main/res/mipmap-*/ic_launcher[_round].png
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
RES = ROOT / 'mobile' / 'android' / 'app' / 'src' / 'main' / 'res'
DRAWABLE = RES / 'drawable-nodpi'

# What the phone renders. The desktop config names these same files; `sad` has no
# image on the desktop either, so it takes the neutral art (see zayabar_config).
EMOTION_FILES = {
    'neutral': 'neutral.png',
    'happy': 'happy.png',
    'angry': 'angry.png',
    'surprised': 'surprised.png',
    'poked': 'poked.png',
    'standby': 'standby.png',
    'sad': 'neutral.png',           # desktop fallback: sad → neutral → standby
}

# Chest-up: the head, shoulders and the top of the dress. Everything below is the
# part a phone screen has no room for anyway.
BODY_VISIBLE_TOP = 0.00
CHEST_BOTTOM = 0.55
PORTRAIT_WIDTH = 720
ICON_BACKGROUND = (27, 30, 39, 255)          # same dark slate the dashboard uses


def _portrait_window(paths: list[Path]) -> tuple[int, int, int, int]:
    """One crop box that contains every emotion: union of the opaque pixels."""
    boxes = []
    for path in paths:
        with Image.open(path) as image:
            boxes.append(image.convert('RGBA').getchannel('A').getbbox())
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    height = bottom - top
    # A square-ish window keeps the character centred when the phone scales it.
    square = max(right - left, int(height * (CHEST_BOTTOM - BODY_VISIBLE_TOP)))
    centre = (left + right) // 2
    half = square // 2
    return (max(0, centre - half), top, max(0, centre - half) + square,
            top + int(height * (CHEST_BOTTOM - BODY_VISIBLE_TOP)))


def build_portraits() -> dict[str, Path]:
    sources = {name: ASSETS / filename for name, filename in EMOTION_FILES.items()}
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise SystemExit(f'Missing desktop assets: {", ".join(sorted(set(missing)))}')

    window = _portrait_window(sorted(set(sources.values())))
    DRAWABLE.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, source in sources.items():
        with Image.open(source) as image:
            portrait = image.convert('RGBA').crop(window)
        ratio = PORTRAIT_WIDTH / portrait.width
        portrait = portrait.resize((PORTRAIT_WIDTH, max(1, round(portrait.height * ratio))),
                                   Image.LANCZOS)
        target = DRAWABLE / f'zaya_{name}.png'
        portrait.save(target, optimize=True)
        written[name] = target
        print(f'  {target.relative_to(ROOT)}  {portrait.width}x{portrait.height}  '
              f'from {source.name}')
    print(f'Crop window (union of every emotion): {window}')
    return written


def _head_window(portrait: Image.Image) -> tuple[int, int, int, int]:
    """The face, squared off, ignoring thin ribbons and outstretched arms.

    The portrait is chest-up, so the head lives in the top third. Taking a plain
    bounding box of that strip would include a shoulder or a dangling ribbon and
    shrink the face to a speck on the launcher icon, so the box is measured from
    the *dense* part of the strip: columns and rows that are mostly opaque.
    """
    strip_height = max(1, int(portrait.height * 0.34))
    strip = portrait.crop((0, 0, portrait.width, strip_height))
    mask = strip.getchannel('A').point(lambda value: 255 if value > 40 else 0)
    columns = [sum(1 for y in range(strip_height) if mask.getpixel((x, y))) for x in range(portrait.width)]
    dense_columns = [x for x, count in enumerate(columns) if count > strip_height * 0.25]
    if not dense_columns:
        return (0, 0, portrait.width, strip_height)
    left, right = min(dense_columns), max(dense_columns) + 1
    rows = [sum(1 for x in range(left, right) if mask.getpixel((x, y))) for y in range(strip_height)]
    dense_rows = [y for y, count in enumerate(rows) if count > (right - left) * 0.12]
    top = min(dense_rows) if dense_rows else 0
    bottom = (max(dense_rows) + 1) if dense_rows else strip_height
    # A little air around the hair, then one square so the icon never distorts.
    pad = int(max(right - left, bottom - top) * 0.10)
    left, top = max(0, left - pad), max(0, top - pad)
    right, bottom = min(portrait.width, right + pad), min(portrait.height, bottom + pad)
    side = max(right - left, bottom - top)
    centre = (left + right) // 2
    half = side // 2
    left = max(0, min(centre - half, portrait.width - side))
    top = max(0, min(top, portrait.height - side))
    return (left, top, left + side, top + side)


def build_icon(portrait_path: Path) -> None:
    """App icon: Zaya's head on the dashboard's dark slate, adaptive + legacy."""
    with Image.open(portrait_path) as image:
        portrait = image.convert('RGBA')
    head = portrait.crop(_head_window(portrait))

    # Adaptive foreground: 108 dp canvas, the art inside the central safe zone.
    canvas = 432
    safe = int(canvas * 0.76)
    scale = min(safe / head.width, safe / head.height)
    head = head.resize((max(1, int(head.width * scale)), max(1, int(head.height * scale))),
                       Image.LANCZOS)
    foreground = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    foreground.alpha_composite(head, ((canvas - head.width) // 2,
                                      (canvas - head.height) // 2))
    target = DRAWABLE / 'ic_launcher_foreground.png'
    foreground.save(target, optimize=True)
    print(f'  {target.relative_to(ROOT)}  {target.stat().st_size // 1024} KB')

    # Legacy launcher icons: the same head on a filled background, one per density.
    for folder, size in (('mdpi', 48), ('hdpi', 72), ('xhdpi', 96),
                         ('xxhdpi', 144), ('xxxhdpi', 192)):
        directory = RES / f'mipmap-{folder}'
        directory.mkdir(parents=True, exist_ok=True)
        for name, circular in (('ic_launcher.png', False), ('ic_launcher_round.png', True)):
            icon = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(icon)
            if circular:
                draw.ellipse((0, 0, size - 1, size - 1), fill=ICON_BACKGROUND)
            else:
                draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 6,
                                       fill=ICON_BACKGROUND)
            inner = int(size * 0.82)
            ratio = min(inner / head.width, inner / head.height)
            art = head.resize((max(1, int(head.width * ratio)), max(1, int(head.height * ratio))),
                              Image.LANCZOS)
            art.putalpha(art.getchannel('A').point(lambda value: int(value * 1.0)))
            icon.alpha_composite(art, ((size - art.width) // 2, (size - art.height) // 2))
            icon.save(directory / name, optimize=True)
        print(f'  mipmap-{folder}/ic_launcher.png + ic_launcher_round.png ({size}px)')


def main() -> int:
    print('Android character art ← desktop assets')
    portraits = build_portraits()
    build_icon(portraits['neutral'])
    print('Done. The app renders the laptop\'s emotion verbatim; this art is only the face.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
