"""Draw the KOMPAS-AI application icon (original artwork).

White round badge with a drafting compass drawing an arc over a dimension
line, and an "AI" tag. Produces kompas_ai.png (1024 px) and kompas_ai.ico.

    python packaging/icon/make_icon.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 1024
NAVY = (24, 46, 84, 255)
ACCENT = (230, 120, 30, 255)
GREY = (190, 196, 206, 255)
HERE = Path(__file__).resolve().parent


def font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw(size=S * 2):
    k = size / S
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # soft shadow + white badge with a thin grey rim
    d.ellipse([60 * k, 76 * k, 980 * k, 996 * k], fill=(0, 0, 0, 40))
    d.ellipse([44 * k, 44 * k, 964 * k, 964 * k], fill=(255, 255, 255, 255),
              outline=GREY, width=int(14 * k))

    cx, top = 504 * k, 205 * k
    # arc being drawn by the compass
    r = 330 * k
    d.arc([cx - r, top + 90 * k, cx + r, top + 90 * k + 2 * r], start=200, end=340,
          fill=ACCENT, width=int(26 * k))

    # compass: pivot, two legs, needle and lead
    spread = math.radians(24)
    length = 520 * k
    for side in (-1, 1):
        x = cx + side * math.sin(spread) * length
        y = top + math.cos(spread) * length
        d.line([cx, top, x, y], fill=NAVY, width=int(54 * k))
        tip = 70 * k
        d.line([x, y, x + side * math.sin(spread) * tip, y + math.cos(spread) * tip],
               fill=NAVY if side < 0 else ACCENT, width=int(22 * k))
    d.ellipse([cx - 62 * k, top - 62 * k, cx + 62 * k, top + 62 * k], fill=NAVY)
    d.ellipse([cx - 24 * k, top - 24 * k, cx + 24 * k, top + 24 * k], fill=(255, 255, 255, 255))
    d.rectangle([cx - 18 * k, top - 150 * k, cx + 18 * k, top - 60 * k], fill=NAVY)

    # dimension line with arrows under the drawing
    y = 820 * k
    x1, x2 = 250 * k, 650 * k
    d.line([x1, y, x2, y], fill=NAVY, width=int(14 * k))
    a = 46 * k
    d.polygon([(x1, y), (x1 + a, y - a / 3), (x1 + a, y + a / 3)], fill=NAVY)
    d.polygon([(x2, y), (x2 - a, y - a / 3), (x2 - a, y + a / 3)], fill=NAVY)

    # "AI" tag
    tx0, ty0, tx1, ty1 = 640 * k, 610 * k, 900 * k, 790 * k
    d.rounded_rectangle([tx0, ty0, tx1, ty1], radius=int(46 * k), fill=NAVY)
    f = font(int(132 * k))
    w = d.textlength("AI", font=f)
    d.text(((tx0 + tx1 - w) / 2, ty0 + 14 * k), "AI", font=f, fill=(255, 255, 255, 255))
    return img.resize((S, S), Image.LANCZOS)


if __name__ == "__main__":
    icon = draw()
    icon.save(HERE / "kompas_ai.png")
    icon.save(HERE / "kompas_ai.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon written to", HERE)
