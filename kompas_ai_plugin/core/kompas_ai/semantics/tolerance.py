"""Tolerances and surface roughness written on a drawing.

A size text is split into what comes before the number (Ø, R, «2 отв. Ø»),
the number and the tolerance after it: deviations (±0,1; -0,2; +0,3;
+0,2/-0,1) or a fit field (h12, H7, js9). For H/h/JS/js the limits follow
from the ISO 286 / ГОСТ 25346 grades; other fields are named but their
deviations are not tabulated here. Roughness marks (Ra 3,2; Rz 20) are found
among the texts.
"""

from __future__ import annotations

import re

SIZE_RE = re.compile(r"^(?P<head>.*?)(?P<num>\d+(?:[.,]\d+)?)(?P<tail>.*)$")
DEV_RE = re.compile(r"([+\-−±])\s*(\d+(?:[.,]\d+)?)")
FIT_RE = re.compile(r"^\s*(?P<field>[A-Za-z]{1,2})(?P<grade>\d{1,2})\b")
ROUGH_RE = re.compile(r"\b(?P<kind>Ra|Rz|Rmax)\s*(?P<value>\d+(?:[.,]\d+)?)")

# IT grades, µm, for sizes up to 3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500 mm
STEPS = (3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500)
IT = {
    6: (6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40),
    7: (10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63),
    8: (14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97),
    9: (25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155),
    10: (40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250),
    11: (60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400),
    12: (100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630),
    13: (140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970),
    14: (250, 300, 360, 430, 520, 620, 740, 870, 1000, 1150, 1300, 1400, 1550),
}


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def num(v: float) -> str:
    """3 decimals at most, comma, no trailing zeros."""
    text = f"{v:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if text not in ("-0", "") else "0"


SIGN_RE = re.compile(r"[Ø⌀∅RМM](?=\s*\d)")
TOL_START_RE = re.compile(r"^\s*(?:[+\-−±]\s*\d+(?:[.,]\d+)?(?![\dA-Za-z])"
                          r"|[A-Za-z]{1,2}\d{1,2}\b)")


def split_size(text: str) -> tuple[str, str, str]:
    """(head, number, tolerance) of a size text: «Ø23-0,2» → («Ø», «23», «-0,2»);
    «2 отв. Ø8H7» → («2 отв. Ø», «8», «H7»). What follows the number and is
    no tolerance (a thread's pitch «×1,5», a mark «*») stays with the number."""
    text = text.strip()
    sign = SIGN_RE.search(text)
    start = sign.end() if sign else 0
    m = SIZE_RE.match(text[start:])
    if not m:
        return text, "", ""
    head = text[:start] + m.group("head")
    tail = m.group("tail")
    if TOL_START_RE.match(tail):
        return head, m.group("num"), tail.strip()
    # «×1,5», «*»…: kept with the number, then perhaps a tolerance
    cut = re.search(r"(?:[+\-−±]\s*\d+(?:[.,]\d+)?(?![\dA-Za-z])"
                    r"|(?<![A-Za-zА-Яа-я\d])[A-Za-z]{1,2}\d{1,2}\b)", tail)
    if cut:
        return head, m.group("num") + tail[:cut.start()], tail[cut.start():].strip()
    return head, m.group("num") + tail, ""


def it_grade(size: float, grade: int) -> float | None:
    """The IT tolerance, mm, of a size (None out of the table)."""
    row = IT.get(grade)
    if row is None or size <= 0 or size > STEPS[-1]:
        return None
    for limit, value in zip(STEPS, row):
        if size <= limit:
            return value / 1000.0
    return None


def deviations(nominal: float, tol: str) -> tuple[float, float] | None:
    """(upper, lower) deviation, mm, of a tolerance text; None when unknown."""
    tol = tol.strip()
    if not tol:
        return None
    fit = FIT_RE.match(tol)
    if fit:
        field, grade = fit.group("field"), int(fit.group("grade"))
        it = it_grade(nominal, grade)
        if it is None:
            return None
        if field == "h":
            return 0.0, -it
        if field == "H":
            return it, 0.0
        if field.lower() == "js":
            return it / 2, -it / 2
        return None
    devs = [(sign, _f(value)) for sign, value in DEV_RE.findall(tol)]
    if not devs:
        return None
    if devs[0][0] == "±":
        return devs[0][1], -devs[0][1]
    values = [v if sign == "+" else -v for sign, v in devs]
    if len(values) == 1:
        return (values[0], 0.0) if values[0] > 0 else (0.0, values[0])
    return max(values), min(values)


def limits_text(nominal: float | None, tol: str) -> str:
    """«22,8 … 23» of «23» «-0,2»; the field named when it is not tabulated."""
    if nominal is None or not tol:
        return ""
    dev = deviations(nominal, tol)
    if dev is None:
        fit = FIT_RE.match(tol)
        return f"поле {fit.group(0)} (ГОСТ 25347)" if fit else ""
    up, low = dev
    return f"{num(nominal + low)} … {num(nominal + up)}"


def middle(nominal: float, tol: str) -> float | None:
    """The middle of the tolerance field (what a part is made to)."""
    dev = deviations(nominal, tol)
    return None if dev is None else nominal + (dev[0] + dev[1]) / 2


def roughness(text: str) -> tuple[str, float] | None:
    """(«Ra»|«Rz»|«Rmax», value) of a roughness mark."""
    m = ROUGH_RE.search(text)
    return (m.group("kind"), _f(m.group("value"))) if m else None
