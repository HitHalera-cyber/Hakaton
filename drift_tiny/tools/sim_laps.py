#!/usr/bin/env python3
"""Drives the CPU autopilot (autopilot_controller.gd) around every track with
the car model from sim_drift.py. Reports lap time, how far the car strays from
the centre line (barriers sit at width/2 + 18 px) and time spent drifting.
No collisions are simulated, so a car that would hit a barrier shows up as a
large max_offset.
Usage: python3 tools/sim_laps.py [car_id ...]
"""
import json, math, os, sys
sys.argv, _args = sys.argv[:1], sys.argv[1:]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_tracks as ct            # noqa: E402
from sim_drift import Car, DT       # noqa: E402
SPACING = 6.0


class Track:
    def __init__(s, t):
        s.width = t["width"]
        s.surface = t["surface"]
        s.s = ct.sample([tuple(p) for p in t["points"]])
        n = len(s.s)
        s.tan, s.nor, s.curv = [], [], []
        for i in range(n):
            a, b = s.s[i - 1], s.s[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            s.tan.append((dx / L, dy / L))
            s.nor.append((-dy / L, dx / L))
        for i in range(n):
            a, b = s.tan[i - 4], s.tan[(i + 4) % n]
            ang = math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])
            s.curv.append(ang / (SPACING * 8))
        s.cum = [0.0]
        for i in range(1, n):
            s.cum.append(s.cum[-1] + math.dist(s.s[i - 1], s.s[i]))
        s.total = s.cum[-1] + math.dist(s.s[-1], s.s[0])

    def nearest(s, p, hint):
        n = len(s.s)
        best, bd = 0, 1e18
        rng = range(hint - 40, hint + 41) if hint >= 0 else range(n)
        for i in rng:
            i %= n
            d = (p[0] - s.s[i][0]) ** 2 + (p[1] - s.s[i][1]) ** 2
            if d < bd:
                bd, best = d, i
        return best

    def advance(s, i, d):
        return (i + int(round(d / SPACING))) % len(s.s)


class Scoring:
    """Port of DriftScoring (scripts/race/drift_scoring.gd)."""

    def __init__(s):
        s.total = 0
        s.current = 0.0
        s.mult = 1.0
        s.chain = 0.0
        s.chain_time = 0.0
        s.in_chain = False
        s.best = 0

    def update(s, dt, drifting, slip, speed, edge):
        if drifting and slip > 12 and speed > 60 and edge > -1:
            angle_f = min(max((slip - 8) / 37, 0), 1.4)
            speed_f = min(max(speed / 200, 0.3), 1.6)
            edge_f = 1.5 if edge < 9 else 1.0
            s.current += 140 * angle_f * speed_f * edge_f * dt
            s.mult = min(s.mult + 0.32 * dt * (1 + int(s.chain_time) // 4 * 0.25), 5.0)
            s.chain = 1.4
            s.chain_time += dt
            s.in_chain = True
        elif s.in_chain:
            s.chain -= dt
            if s.chain <= 0:
                pts = int(s.current * s.mult * 1.15)
                s.total += pts
                s.best = max(s.best, pts)
                s.current, s.mult, s.in_chain, s.chain_time = 0.0, 1.0, False, 0.0


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def run(track_def, car_def, skill=1.0, laps=2):
    tr = Track(track_def)
    grip_mult = {"asphalt": 1.0, "wet": 0.86, "dirt": 0.8, "snow": 0.72}[tr.surface]
    if car_def.get("loose_surface_bonus", 0) and tr.surface in ("dirt", "snow"):
        grip_mult += (1 - grip_mult) * car_def["loose_surface_bonus"]
    c = Car(car_def)
    i0 = len(tr.s) - 6
    x, y = tr.s[i0]
    c.rot = math.atan2(tr.tan[i0][1], tr.tan[i0][0])
    idx = i0
    prev_d = tr.cum[idx]
    travelled = -(tr.total - prev_d)
    t = 0.0
    max_off = 0.0
    drift_t = 0.0
    hb_t = 0.0
    lap_times = []
    lap_start = 0.0
    score = Scoring()
    import random
    rnd = random.Random(3)
    while len(lap_times) < laps and t < 400:
        speed = math.hypot(c.vx, c.vy)
        look = min(max(speed * 0.32, 22.0), 80.0)
        a = tr.advance(idx, look)
        tx, ty = tr.s[a]
        to_ang = math.atan2(ty - y, tx - x)
        diff = wrap(to_ang - c.rot)
        steer = max(-1.0, min(1.0, diff * 2.6))
        if c.drifting and speed > 30:
            # Cascade: pick the drift angle that bends the path towards the
            # target, then steer to hold that angle (counter-steer included).
            vel_ang = math.atan2(c.vy, c.vx)
            beta = wrap(c.rot - vel_ang)
            want = max(-0.6, min(0.6, wrap(to_ang - vel_ang) * 1.5))
            steer = max(-1.0, min(1.0, (want - beta) * 2.5))
        bend = max(abs(tr.curv[tr.advance(idx, look * 0.6 * k)]) for k in (1, 2, 3, 4))
        radius = 1.0 / max(bend, 1e-4)
        maxs = car_def["max_speed"] * skill
        target = min(max(math.sqrt(radius) * 15.0 * skill, 90.0), maxs)
        target *= math.sqrt(grip_mult)
        if c.drifting:
            target *= 0.85
        if speed < target:
            thr, brk = 1.0, 0.0
        elif speed > target + 25:
            thr, brk = 0.0, min(max((speed - target) / 80, 0.2), 1.0)
        else:
            thr, brk = 0.4, 0.0
        if hb_t > 0:
            hb_t -= DT
            hb = True
        else:
            hb = False
            if radius < 120 and speed > 150 and abs(diff) > 0.25 and rnd.random() < 0.5 * DT * 6:
                hb_t = 0.22
        c.step(thr, brk, steer, hb, grip_mult)
        x += c.vx * DT
        y += c.vy * DT
        t += DT
        idx = tr.nearest((x, y), idx)
        off = abs((x - tr.s[idx][0]) * tr.nor[idx][0] + (y - tr.s[idx][1]) * tr.nor[idx][1])
        score.update(DT, c.drifting, c.slip, math.hypot(c.vx, c.vy), tr.width / 2 - off)
        max_off = max(max_off, off)
        if c.drifting:
            drift_t += DT
        d = tr.cum[idx]
        step = d - prev_d
        if step < -tr.total / 2:
            step += tr.total
        elif step > tr.total / 2:
            step -= tr.total
        prev_d = d
        travelled += step
        if travelled >= (len(lap_times) + 1) * tr.total:
            lap_times.append(t - lap_start)
            lap_start = t
    wall = tr.width / 2 + 18
    status = "OK" if max_off < wall - 4 and len(lap_times) == laps else ("HITS WALL" if max_off >= wall - 4 else "DNF")
    return lap_times, max_off, wall, drift_t, status, score


def main():
    cars = json.load(open(os.path.join(HERE, "..", "data", "cars.json")))["cars"]
    tracks = json.load(open(os.path.join(HERE, "..", "data", "tracks.json")))["tracks"]
    ids = _args or ["classic", "jdm", "sport"]
    for t in tracks:
        for car in cars:
            if car["id"] not in ids:
                continue
            laps, off, wall, dt, st, sc = run(t, car)
            lt = " ".join(f"{v:5.1f}s" for v in laps)
            print(f"{t['id']:9s} {car['id']:8s} laps: {lt:16s} max_offset={off:5.1f}/{wall:.0f}px "
                  f"drift={dt:5.1f}s points/lap={sc.total // max(len(laps), 1):6d} best_combo={sc.best:6d}  {st}")


main()
