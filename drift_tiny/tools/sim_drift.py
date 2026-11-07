#!/usr/bin/env python3
"""Offline port of Car._physics_process (scripts/race/car.gd) for tuning.

Runs scripted manoeuvres and prints speed / slip angle / drift state so the
handling numbers in data/cars.json can be checked without opening Godot.
Keep in sync with car.gd when the model changes.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DT = 1 / 60
DRAG = 0.22
ROLL = 35.0
DRIFT_YAW = 2.8
ALIGN = 1.2
HB_YAW = 2.4
POWER_YAW = 1.4
DRIFT_FRICTION = 130.0
BOOST_CHARGE = [0.5, 1.2, 2.2]
BOOST_POWER = [0.15, 0.25, 0.35]
BOOST_TIME = [0.6, 0.9, 1.3]


class Car:
    def __init__(s, st):
        s.st = st
        s.rot = 0.0
        s.vx = s.vy = 0.0
        s.ang = 0.0
        s.drifting = False
        s.exit_t = 0.0
        s.slip = 0.0
        s.spun = False
        s.charge = 0.0
        s.boost_t = 0.0
        s.boost_p = 0.0
        s.boosts = 0

    def step(s, thr, brk, steer, hb, grip_mult=1.0):
        st = s.st
        speed = math.hypot(s.vx, s.vy)
        vel_ang = math.atan2(s.vy, s.vx)
        fx, fy = math.cos(s.rot), math.sin(s.rot)
        rx, ry = -fy, fx
        vl = s.vx * fx + s.vy * fy
        vt = s.vx * rx + s.vy * ry
        if s.boost_t > 0:
            s.boost_t -= DT
        boost = s.boost_p if s.boost_t > 0 else 0.0
        maxs = st["max_speed"] * (1 + boost)
        if thr > 0:
            if vl < -5:
                vl += st["brake"] * thr * DT
            else:
                f = max(0.0, 1 - (max(vl, 0) / maxs) ** 2)
                vl += st["accel"] * (1 + boost * 3) * thr * f * DT
        if brk > 0:
            if vl > 5:
                vl -= st["brake"] * brk * DT
            else:
                vl = max(vl - st["accel"] * 0.5 * brk * DT, -maxs * 0.35)
        vl -= vl * DRAG * DT
        if thr == 0 and brk == 0:
            vl = move_toward(vl, 0, ROLL * DT)
        if hb:
            vl = move_toward(vl, 0, st["brake"] * 0.3 * DT)
        slip_full = math.degrees(math.atan2(abs(vt), vl)) if speed > 1.0 else 0.0
        slip = min(slip_full, 90.0)
        # drift state
        was = s.drifting
        if hb and speed > 50:
            s.drifting = True
        if (not s.drifting and speed > maxs * 0.45 and abs(steer) > 0.7 and thr > 0.8
                and slip > 13 - 10 * st["power_slide"]):
            s.drifting = True
        if s.drifting:
            if slip < 7 and not hb:
                s.exit_t += DT
                if s.exit_t > 0.3:
                    s.drifting = False
            else:
                s.exit_t = 0
            if speed < 35:
                s.drifting = False
        # yaw
        dirs = 1.0 if vl >= -2 else -1.0
        sf = min(abs(vl) / 70, 1.0)
        if s.drifting:
            # Steering and throttle open the drift angle (beta), the tyres
            # pull it back towards zero: a stable, holdable slide.
            beta = wrap_angle(s.rot - vel_ang) if speed > 1 else 0.0
            target = steer * DRIFT_YAW * st["drift_steer"] * max(sf, 0.6)
            target += sign(beta) * thr * st["power_slide"] * POWER_YAW * min(abs(beta) / 0.45, 1.0)
            align = ALIGN / st["drift_stability"]
            if hb:
                # Locked rear wheels: the car pivots around the front.
                target += steer * HB_YAW
                align *= 0.3
            target -= align * beta
            resp = 6.0
        else:
            hs = 1 - 0.45 * min(speed / maxs, 1)
            target = steer * st["steer"] * sf * hs * dirs
            resp = 12.0
        s.ang += (target - s.ang) * (1 - math.exp(-resp * DT))
        if s.drifting and slip > 12 and speed > 60:
            s.charge += DT
        if was and not s.drifting:
            lvl = sum(1 for c in BOOST_CHARGE if s.charge >= c)
            s.charge = 0.0
            if lvl:
                s.boost_t, s.boost_p = BOOST_TIME[lvl - 1], BOOST_POWER[lvl - 1]
                s.boosts += 1
        # lateral grip
        if s.drifting:
            # Sliding tyres give a roughly constant sideways force (past the
            # grip peak), so the slide can still follow a tight corner.
            acc = st["drift_grip"] * DRIFT_FRICTION * (0.55 if hb else 1.0) * grip_mult
            acc *= 1.0 + max(slip - 50.0, 0.0) * 0.02 * st["drift_stability"]
            new_vt = move_toward(vt, 0.0, acc * DT)
            keep = st["drift_keep"]
        else:
            new_vt = vt * math.exp(-st["grip"] * grip_mult * DT)
            keep = 0.8
        # Part of the sideways speed the tyres take away turns into forward
        # speed (energy-wise, so cornering never adds speed).
        if vl >= 0:
            vl = math.sqrt(vl * vl + (vt * vt - new_vt * new_vt) * keep)
        vt = new_vt
        if s.drifting:
            vl -= vl * 0.35 * min(slip / 45, 1.5) * DT
        # recompose in the basis the components were measured in; the heading
        # turns afterwards, which is what opens up the slip angle
        s.vx = fx * vl + rx * vt
        s.vy = fy * vl + ry * vt
        sp = math.hypot(s.vx, s.vy)
        cap = st["max_speed"] * 1.05 * (1 + boost)
        if sp > cap:
            s.vx *= cap / sp
            s.vy *= cap / sp
        s.rot += s.ang * DT
        s.slip = slip
        if slip_full > 110 and s.drifting:
            s.spun = True
            s.drifting = False
            s.charge = 0.0
        return speed


def move_toward(a, b, d):
    if abs(b - a) <= d:
        return b
    return a + math.copysign(d, b - a)


def wrap_angle(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def sign(x):
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def run(st, name, script):
    c = Car(st)
    t = 0.0
    log = []
    max_slip = 0
    drift_time = 0
    for (dur, thr, brk, steer, hb) in script:
        n = int(dur / DT)
        for _ in range(n):
            sp = c.step(thr, brk, steer, hb)
            t += DT
            if c.drifting:
                drift_time += DT
                max_slip = max(max_slip, c.slip)
        log.append(f"{t:4.1f}s v={math.hypot(c.vx, c.vy):5.0f} slip={c.slip:5.1f} drift={'Y' if c.drifting else '-'}")
    print(f"  {name:28s} max_slip={max_slip:5.1f} drift_time={drift_time:4.1f}s spun={c.spun}")
    for l in log:
        print("     ", l)


def main():
    data = json.load(open(os.path.join(HERE, "..", "data", "cars.json")))
    ids = sys.argv[1:] or [c["id"] for c in data["cars"]]
    for car in data["cars"]:
        if car["id"] not in ids:
            continue
        print(car["id"])
        run(car, "accelerate 6s", [(2, 1, 0, 0, False), (2, 1, 0, 0, False), (2, 1, 0, 0, False)])
        run(car, "full-lock corner, no hb", [(4, 1, 0, 0, False), (1.5, 1, 0, 1, False), (1.5, 1, 0, 0, False)])
        run(car, "handbrake flick + hold", [(4, 1, 0, 0, False), (0.25, 1, 0, 1, True), (1.5, 1, 0, 0.6, False), (1.0, 1, 0, -0.3, False), (1.0, 1, 0, 0, False)])
        run(car, "handbrake + countersteer", [(4, 1, 0, 0, False), (0.3, 0.5, 0, 1, True), (0.6, 1, 0, -0.4, False), (1.0, 0.6, 0, 0.2, False), (1.2, 1, 0, 0, False)])
        run(car, "brake from top speed", [(6, 1, 0, 0, False), (1.0, 0, 1, 0, False)])


if __name__ == "__main__":
    main()
