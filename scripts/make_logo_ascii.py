"""Turn the profile logo into ASCII art (run by hand when the logo changes).

    pip install pillow
    python scripts/make_logo_ascii.py            # reads assets/logo-source.jpg

Writes data/logo_ascii.txt, which scripts/render_cards.py draws into the hero card.
The logo is a saturated blue mark on a pale background, so "ink" is measured as
colour saturation times darkness rather than plain brightness.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "assets", "logo-source.jpg")
OUT = os.path.join(HERE, "..", "data", "logo_ascii.txt")

COLS = 58
RAMP = " .:-=+*#%@"  # empty -> dense
CROP = 0.17          # trim the empty border of the avatar

im = Image.open(SRC).convert("RGB")
w, h = im.size
im = im.crop((int(w * CROP), int(h * CROP), int(w * (1 - CROP)), int(h * (1 - CROP))))
rows = round(COLS * 0.5)  # a character cell is about twice as tall as wide
im = im.resize((COLS, rows), Image.LANCZOS)

lines = []
for y in range(rows):
    out = []
    for x in range(COLS):
        r, g, b = im.getpixel((x, y))
        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0 if mx == 0 else (mx - mn) / mx
        if sat < 0.45:
            out.append(" ")
            continue
        dark = 1 - (0.299 * r + 0.587 * g + 0.114 * b) / 255
        t = min(1.0, max(0.0, (dark - 0.45) / 0.45))
        out.append(RAMP[2 + round(t * (len(RAMP) - 3))])
    lines.append("".join(out).rstrip())

while lines and not lines[0].strip():
    lines.pop(0)
while lines and not lines[-1].strip():
    lines.pop()
indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
lines = [l[indent:] for l in lines]

with open(OUT, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"wrote {OUT}: {len(lines)} rows x {max(map(len, lines))} cols")
