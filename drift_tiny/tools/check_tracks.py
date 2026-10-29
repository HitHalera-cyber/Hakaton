#!/usr/bin/env python3
"""Validates track geometry from data/tracks.json (same spline maths as track_data.gd).

Checks: minimum turning radius (the inner road edge must not fold) and the
clearance between parts of the track that are far apart along the road
(two road sections + their barriers must not overlap).
Usage: python3 tools/check_tracks.py [--png out_dir]
"""
import json, math, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SPACING = 6.0
WALL_MARGIN = 18.0


def catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(2))


def sample(points):
    n = len(points)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        steps = max(2, math.ceil(math.dist(p1, p2) / SPACING))
        for s in range(steps):
            out.append(catmull(p0, p1, p2, p3, s / steps))
    return out


def check(track):
    pts = [tuple(p) for p in track["points"]]
    w = track["width"]
    s = sample(pts)
    n = len(s)
    ok = True
    # turning radius from three points 5 samples apart
    min_r = 1e9
    for i in range(n):
        a, b, c = s[i - 5], s[i], s[(i + 5) % n]
        ab, bc, ca = math.dist(a, b), math.dist(b, c), math.dist(c, a)
        area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        if area2 > 1e-6:
            min_r = min(min_r, ab * bc * ca / (2 * area2))
    need_r = w / 2 + 10
    if min_r < need_r:
        ok = False
    # clearance between far-apart samples
    need_gap = w + 2 * WALL_MARGIN + 16
    min_gap = 1e9
    where = None
    cum = [0.0]
    for i in range(1, n):
        cum.append(cum[-1] + math.dist(s[i - 1], s[i]))
    total = cum[-1] + math.dist(s[-1], s[0])
    for i in range(0, n, 2):
        for j in range(i + 1, n, 2):
            along = abs(cum[j] - cum[i])
            along = min(along, total - along)
            if along < need_gap * 2.2:
                continue
            d = math.dist(s[i], s[j])
            if d < min_gap:
                min_gap, where = d, (s[i], s[j])
    if min_gap < need_gap:
        ok = False
    print(f"{track['id']:10s} samples={n:4d} length={total:7.0f}px  min_radius={min_r:6.1f} (need {need_r:.0f})"
          f"  min_gap={min_gap:6.1f} (need {need_gap:.0f}) at {where and tuple(round(v) for v in where[0])}"
          f"  {'OK' if ok else 'FAIL'}")
    return ok, s


def render(track, s, out_dir):
    from PIL import Image, ImageDraw
    xs = [p[0] for p in s]; ys = [p[1] for p in s]
    W, H = int(max(xs) + 200), int(max(ys) + 200)
    img = Image.new("RGB", (W // 2, H // 2), (30, 60, 40))
    d = ImageDraw.Draw(img)
    w = track["width"]
    for i in range(len(s)):
        a, b = s[i], s[(i + 1) % len(s)]
        d.line([(a[0] / 2, a[1] / 2), (b[0] / 2, b[1] / 2)], fill=(90, 90, 100), width=int(w / 2))
    for i, p in enumerate(track["points"]):
        d.text((p[0] / 2, p[1] / 2), str(i), fill=(255, 255, 0))
    d.ellipse([s[0][0] / 2 - 4, s[0][1] / 2 - 4, s[0][0] / 2 + 4, s[0][1] / 2 + 4], fill=(255, 0, 0))
    img.save(os.path.join(out_dir, track["id"] + ".png"))


def main():
    with open(os.path.join(HERE, "..", "data", "tracks.json"), encoding="utf-8") as f:
        tracks = json.load(f)["tracks"]
    out = None
    if "--png" in sys.argv:
        out = sys.argv[sys.argv.index("--png") + 1]
    all_ok = True
    for t in tracks:
        ok, s = check(t)
        all_ok &= ok
        if out:
            render(t, s, out)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
