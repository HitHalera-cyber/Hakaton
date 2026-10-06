"""PDF (or drawing.json) → editable KOMPAS drawing, in one command (Windows).

    py -m kompas_ai.to_kompas чертёж.pdf
    py -m kompas_ai.to_kompas drawing.json -o чертёж.cdw
    py -m kompas_ai.to_kompas чертёж.pdf --mode view     # вид с масштабом (нужна лицензия)

KOMPAS opens with the new drawing; it is also saved as .cdw.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ir import Drawing
from .report.summary import summary_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Построить чертёж в КОМПАС по PDF")
    parser.add_argument("source", type=Path, help="PDF чертежа или drawing.json")
    parser.add_argument("-o", "--out", type=Path, default=None, help="куда сохранить .cdw")
    parser.add_argument("--mode", choices=("sheet", "view"), default="sheet",
                        help="sheet — в мм листа (работает без лицензии); view — вид с масштабом")
    parser.add_argument("--page", type=int, default=0)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not args.source.exists():
        print(f"Файл не найден: {args.source}")
        return 2
    if args.source.suffix.lower() == ".json":
        drawing = Drawing.load_json(args.source)
    else:
        from .pipeline import recognize_pdf
        drawing = recognize_pdf(args.source, args.page)
    print(summary_text(drawing))
    print()

    if sys.platform != "win32":
        print("Запись в КОМПАС возможна только в Windows с установленным КОМПАС-3D.")
        return 2
    from .kompas.api5 import Api5Backend
    from .kompas.writer import DrawingWriter

    out = (args.out or args.source.with_name(args.source.stem + "_kompas.cdw")).resolve()
    print("Подключаюсь к КОМПАС (первый запуск может занять 1–3 минуты)...", flush=True)
    backend = Api5Backend()
    report = DrawingWriter(backend, mode=args.mode).write(drawing)
    saved = backend.save(str(out))
    print(report.text())
    print(f"Сохранено: {out}" if saved else f"Не удалось сохранить {out} (код {backend.last_error()})")
    (out.with_suffix(".txt")).write_text(summary_text(drawing) + "\n\n" + report.text() + "\n",
                                         encoding="utf-8")
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
