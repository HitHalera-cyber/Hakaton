"""Triangle meshes of simple parts, as KOMPAS would save them to STL."""
import math
import struct

import numpy as np


def revolve(profile, n=72):
    """A body turned around the X axis: ``profile`` = closed [(x, r), …] in
    order around the section (r ≥ 0)."""
    tris = []
    ring = [(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)) for k in range(n)]
    pts = list(profile) + [profile[0]]
    for (x1, r1), (x2, r2) in zip(pts, pts[1:]):
        for k in range(n):
            (c1, s1), (c2, s2) = ring[k], ring[(k + 1) % n]
            a, b = (x1, r1 * c1, r1 * s1), (x1, r1 * c2, r1 * s2)
            c, d = (x2, r2 * c2, r2 * s2), (x2, r2 * c1, r2 * s1)
            if r1 > 1e-9:
                tris.append((a, b, c))
            if r2 > 1e-9:
                tris.append((a, c, d))
    return np.array(tris, dtype=float)


def plate_with_hole(w, h, t, r, n=64):
    """A w × h plate t thick (Z from 0 to t) with a through hole of radius r in
    its middle, X right, Y up."""
    def outer(k):  # the square's point at the hole point's angle
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        f = min(w / 2 / abs(c) if abs(c) > 1e-12 else 1e9, h / 2 / abs(s) if abs(s) > 1e-12 else 1e9)
        return (c * f, s * f)

    def inner(k):
        a = 2 * math.pi * k / n
        return (r * math.cos(a), r * math.sin(a))

    corners = [(w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2), (w / 2, -h / 2)]
    tris = []
    for z, up in ((0.0, False), (t, True)):
        for k in range(n):
            o1, o2, i1, i2 = outer(k), outer(k + 1), inner(k), inner(k + 1)
            q = [(*i1, z), (*o1, z), (*o2, z), (*i2, z)]
            tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])] if up else \
                [(q[0], q[2], q[1]), (q[0], q[3], q[2])]
        # the corners the angular strips cut off
        for k in range(n):
            a1, a2 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            for cx, cy in corners:
                ac = math.atan2(cy, cx) % (2 * math.pi)
                if a1 < ac < a2:
                    o1, o2 = outer(k), outer(k + 1)
                    tri = [(*o1, z), (cx, cy, z), (*o2, z)]
                    tris.append(tuple(tri) if not up else (tri[0], tri[2], tri[1]))
    # sides: the square's walls and the hole's wall
    outline = []
    for k in range(n):
        a1, a2 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        outline.append(outer(k))
        for cx, cy in corners:
            if a1 < math.atan2(cy, cx) % (2 * math.pi) < a2:
                outline.append((cx, cy))
    for loop, sign in ((outline, 1), ([inner(k) for k in range(n)], -1)):
        for p, q in zip(loop, loop[1:] + loop[:1]):
            a, b, c, d = (*p, 0.0), (*q, 0.0), (*q, t), (*p, t)
            tris += [(a, b, c), (a, c, d)] if sign > 0 else [(a, c, b), (a, d, c)]
    return np.array(tris, dtype=float)


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for t in tris:
            n = np.cross(t[1] - t[0], t[2] - t[0])
            n = n / (np.linalg.norm(n) or 1.0)
            f.write(struct.pack("<12fH", *n, *t.ravel(), 0))
