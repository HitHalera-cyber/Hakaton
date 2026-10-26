"""What the AI model is asked about a drawing, and what it may change.

The geometry stays the program's: a language model misreads numbers and
coordinates by millimetres. The model is shown the sheet (an image) and what
was recognised, and answers the questions the program has: which object a
number without a dimension line measures (only from the candidates found),
which of two contradicting sizes to trust, what kind of part this is. Its
answer is a list of suggestions; the user ticks the ones to apply.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .. import ir
from ..semantics.orphans import key_of

SYSTEM = (
    "Ты — опытный инженер-конструктор. Программа распознала чертёж детали из PDF или фото и "
    "просит проверить спорные места. Тебе дано изображение листа и то, что программа "
    "распознала. Не придумывай числа и объекты: выбирай только из перечисленных вариантов. "
    "Если не уверен — ставь null. Отвечай строго одним JSON-объектом по схеме:\n"
    '{"body": "вращения" | "призматическая" | null, "body_why": "коротко почему",\n'
    ' "orphans": [{"id": "T4", "choice": 1 | "text" | null, "why": "коротко"}],\n'
    ' "conflicts": [{"id": "D3", "trust": "drawing" | "lines" | null, "why": "коротко"}],\n'
    ' "notes": ["замечания по чертежу: допуски, шероховатость, что распознано неверно"],\n'
    ' "questions": ["что спросить у пользователя, если без этого не обойтись"]}\n'
    "Пиши по-русски, коротко.")


def context(drawing: ir.Drawing) -> str:
    """What the program recognised, as the model reads it."""
    from ..gui.refine import dimension_rows, orphan_rows, roughness_rows

    lines = [f"Лист {drawing.sheet.format}, масштаб {drawing.scale.text}."]
    verdict = getattr(drawing, "model_verdict", None)
    if verdict:
        lines.append(f"Программа считает: {verdict[1]}.")
    rows = dimension_rows(drawing)
    if rows:
        lines.append("Размеры (id: надпись → по линиям, мм):")
        for r in rows:
            got = "—" if r["lines"] is None else f"{r['lines']:.2f}"
            mark = " ПРОТИВОРЕЧИТ ДРУГИМ" if r["conflict"] else ""
            lines.append(f"  {r['id']}: «{r['text']}» → {got}{mark}")
    orphans = orphan_rows(drawing)
    if orphans:
        lines.append("Числа без размерной линии — что каждое измеряет? Варианты:")
        for o in orphans:
            lines.append(f"  {o['id']}: «{o['text']}»")
            for k, c in enumerate(o["candidates"], 1):
                lines.append(f"    {k}) {c['label']}")
            if not o["candidates"]:
                lines.append("    (подходящих объектов не найдено)")
    rough = roughness_rows(drawing)
    if rough:
        lines.append("Шероховатость: " + "; ".join(f"{r['id']} «{r['text']}»" for r in rough))
    texts = [t.text for t in drawing.of_type(ir.Text)][:30]
    if texts:
        lines.append("Прочие надписи: " + "; ".join(f"«{t}»" for t in texts))
    for w in drawing.warnings[:8]:
        lines.append("Предупреждение: " + w[:200])
    return "\n".join(lines)


@dataclass
class Suggestion:
    kind: str  # attach | value | info
    target: str  # the id it is about ("" for a note)
    label: str  # what the window shows
    why: str = ""
    payload: dict = field(default_factory=dict)

    @property
    def applicable(self) -> bool:
        return self.kind in ("attach", "value")


def parse(answer: str) -> dict:
    """The JSON object in the model's answer (models wrap it in text at times)."""
    try:
        return json.loads(answer)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"\{.*\}", answer or "", re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def suggestions(drawing: ir.Drawing, data: dict) -> list[Suggestion]:
    """The model's answer checked against the drawing: only choices among the
    candidates, only sizes that exist."""
    from ..gui.refine import dimension_rows, orphan_rows

    out: list[Suggestion] = []
    orphans = {o["id"]: o for o in orphan_rows(drawing)}
    for item in data.get("orphans") or []:
        if not isinstance(item, dict):
            continue
        o = orphans.get(str(item.get("id")))
        choice, why = item.get("choice"), str(item.get("why") or "")
        if o is None or choice is None:
            continue
        if choice == "text":
            out.append(Suggestion("attach", o["id"], f"«{o['text']}» — это просто текст", why,
                                  {"attach": None}))
            continue
        try:
            k = int(choice)
        except (TypeError, ValueError):
            continue
        if 1 <= k <= len(o["candidates"]):
            c = o["candidates"][k - 1]
            out.append(Suggestion("attach", o["id"], f"«{o['text']}» — {c['label']}", why,
                                  {"attach": key_of(c)}))
    rows = {r["id"]: r for r in dimension_rows(drawing)}
    for item in data.get("conflicts") or []:
        if not isinstance(item, dict):
            continue
        r = rows.get(str(item.get("id")))
        trust, why = item.get("trust"), str(item.get("why") or "")
        if r is None or trust not in ("drawing", "lines"):
            continue
        if trust == "lines" and r["lines"] is not None:
            value = round(r["lines"], 2)
            out.append(Suggestion("value", r["id"], f"{r['id']} «{r['text']}»: верить линиям "
                                  f"({value:g})", why, {"value": value}))
        elif trust == "drawing" and r["original"] is not None:
            out.append(Suggestion("info", r["id"], f"{r['id']} «{r['text']}»: верить числу на "
                                  "чертеже (другие размеры проверьте)", why))
    body = data.get("body")
    if body in ("вращения", "призматическая"):
        kind = "тело вращения" if body == "вращения" else "призматическая"
        out.append(Suggestion("info", "", f"Тип детали: {kind}", str(data.get("body_why") or "")))
    for note in data.get("notes") or []:
        if isinstance(note, str) and note.strip():
            out.append(Suggestion("info", "", note.strip()))
    for q in data.get("questions") or []:
        if isinstance(q, str) and q.strip():
            out.append(Suggestion("info", "", "Вопрос: " + q.strip()))
    return out


def ask(drawing: ir.Drawing, image: bytes | None, model: str, url: str) -> list[Suggestion]:
    """The model's suggestions for the drawing (slow: tens of seconds to minutes)."""
    from .ollama import chat, sees_images

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": context(drawing)}]
    images = [image] if image and sees_images(model) else []
    answer = chat(messages, model, url, images=images, json_mode=True)
    return suggestions(drawing, parse(answer))


def free_question(drawing: ir.Drawing, image: bytes | None, question: str, model: str,
                  url: str) -> str:
    """The user's own question about the drawing; a plain answer."""
    from .ollama import chat, sees_images

    messages = [{"role": "system", "content": "Ты — опытный инженер-конструктор. Отвечай по-"
                 "русски, коротко и по делу. Вот что программа распознала на чертеже:\n"
                 + context(drawing)},
                {"role": "user", "content": question}]
    images = [image] if image and sees_images(model) else []
    return chat(messages, model, url, images=images)
