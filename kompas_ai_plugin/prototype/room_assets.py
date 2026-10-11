"""Make the pictures of the waiting screen from the concept image.

    python room_assets.py concept.png ../core/kompas_ai/gui/assets

The concept (a pixel-art room at dawn, the man in his chair by the window)
is boxed down to 384 × 216 pixels and reduced to one small palette. Out
come: the room without the man (room_bg.png) — his place filled with what
stands behind him: the posts of the window go on down, the city and the
water go on from the glass to their right, the sill, the cabinet and the
floor go on row by row, the wall between the desk and the window is its own
colour —, the same room without the mug on the desk (room_nomug.png, while
he drinks), and the man with his chair cut out (room_man.png, transparent
around), as he sits on the concept: feet on the sill.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 384, 216
COLORS = 96

# the man and the chair on the 384 × 216 concept
MAN = [(103, 77), (117, 70), (133, 72), (141, 82), (142, 95), (152, 102), (172, 106),
       (196, 101), (201, 96), (209, 96), (216, 103), (214, 125), (199, 133), (182, 140),
       (180, 152), (178, 168), (182, 178), (176, 205), (150, 206), (116, 206), (99, 192),
       (97, 170), (100, 140), (102, 110), (103, 95)]
POSTS = list(range(126, 137)) + list(range(150, 161))  # the lit wall edge, the window post
MUG = (60, 107, 77, 121)  # x0, y0, x1, y1


def clean(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    res = img.copy()
    known = ~mask.copy()

    def from_right(y, x0, x1, span, skip=()):
        xs = [x for x in range(x0, x1 + 1) if mask[y, x] and x not in skip]
        if not xs:
            return
        right = max(xs) + 1
        for x in xs:
            k = (right - 1 - x) % (2 * span)
            res[y, x] = img[y, right + (k if k < span else 2 * span - 1 - k)]
            known[y, x] = True

    for x in POSTS:  # straight down
        for y in range(60, 128):
            if mask[y, x]:
                res[y, x] = img[48 + (y - 60) % 20, x]
                known[y, x] = True
    for y in range(60, 127):
        from_right(y, 137, 216, 36, skip=POSTS)
    for y in range(127, 172):
        from_right(y, 120, 216, 30)
    for y in range(172, 207):
        from_right(y, 120, 216, 28)
    wall = img[52:60, 118:125].reshape(-1, 3).mean(axis=0)
    for y in range(60, 207):
        xs = [x for x in range(96, 127) if mask[y, x] and not known[y, x]]
        if not xs:
            continue
        x0, x1 = min(xs), max(xs)
        left, right = img[y, x0 - 1], (wall if y < 127 else res[y, x1 + 1])
        for x in xs:
            k = (x - x0 + 1) / (x1 - x0 + 2)
            res[y, x] = left * (1 - k) + right * k
            known[y, x] = True
    todo = mask & ~known
    while todo.any():  # what is left: from its neighbours
        acc = np.zeros_like(res)
        n = np.zeros(mask.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            acc += np.roll(np.roll(res, dy, 0), dx, 1) * np.roll(np.roll(known, dy, 0), dx, 1)[..., None]
            n += np.roll(np.roll(known, dy, 0), dx, 1)
        fill = todo & (n > 0)
        res[fill] = acc[fill] / n[fill][:, None]
        known |= fill
        todo &= ~fill
    return res


def without_mug(img: np.ndarray) -> np.ndarray:
    out = img.copy()
    x0, y0, x1, y1 = MUG
    for y in range(y0, y1 - 2):  # the wall and the tower's foot behind it
        out[y, x0:x1] = img[y0 - 8 + (y - y0) % 8, x0:x1]
    for y in range(y1 - 2, y1):  # the desk top under it
        left, right = img[y, x0 - 1], img[y, x1]
        for x in range(x0, x1):
            k = (x - x0 + 1) / (x1 - x0 + 1)
            out[y, x] = left * (1 - k) + right * k
    return out


def main(src: str, out_dir: str) -> None:
    out = Path(out_dir)
    img = np.asarray(Image.open(src).convert("RGB").resize((W, H), Image.BOX)).astype(float)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(MAN, fill=255)
    mask = np.asarray(m) > 0
    bg = clean(img, mask)
    nomug = without_mug(bg)
    # one palette for all, no dithering: the concept is dithered already
    sheet = Image.fromarray(np.vstack([bg, img]).clip(0, 255).astype(np.uint8))
    pal = sheet.quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT)

    def q(a):
        return Image.fromarray(a.clip(0, 255).astype(np.uint8)).quantize(
            palette=pal, dither=Image.Dither.NONE).convert("RGB")

    q(bg).save(out / "room_bg.png")
    q(nomug).save(out / "room_nomug.png")
    man = np.asarray(q(img))
    Image.fromarray(np.dstack([man, mask.astype(np.uint8) * 255]), "RGBA").save(out / "room_man.png")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
