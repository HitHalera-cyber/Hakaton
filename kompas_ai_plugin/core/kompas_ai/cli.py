"""Command line: recognise a PDF drawing and write all outputs.

    python -m kompas_ai.cli drawing.pdf -o result/ [--reference drawing.dxf]

Writes into the output folder:
    drawing.json   — Drawing IR (input of the KOMPAS writer)
    drawing.dxf    — the same drawing as DXF
    preview.png    — source + recognised objects
    report.txt     — summary, items to review, comparison with the reference
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .evaluation.compare_dxf import compare
from .export.dxf_writer import write_dxf
from .pipeline import recognize_pdf
from .report.preview import render_preview
from .report.summary import summary_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Распознавание чертежа из PDF")
    parser.add_argument("pdf", type=Path, help="векторный PDF чертежа")
    parser.add_argument("-o", "--out", type=Path, default=None,
                        help="папка для результатов (по умолчанию <имя pdf>_result)")
    parser.add_argument("--page", type=int, default=0, help="номер страницы, с 0")
    parser.add_argument("--reference", type=Path, default=None,
                        help="эталонный DXF того же чертежа для оценки точности")
    parser.add_argument("--no-preview", action="store_true", help="не строить preview.png")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not args.pdf.exists():
        print(f"Файл не найден: {args.pdf}")
        return 2
    out = args.out or args.pdf.with_name(args.pdf.stem + "_result")
    out.mkdir(parents=True, exist_ok=True)

    drawing = recognize_pdf(args.pdf, args.page)
    drawing.save_json(out / "drawing.json")
    write_dxf(drawing, out / "drawing.dxf")
    if not args.no_preview:
        render_preview(drawing, args.pdf, out / "preview.png", args.page)

    report = summary_text(drawing)
    if args.reference:
        report += "\n\nСравнение с эталоном " + args.reference.name + "\n" + "=" * 40 + "\n"
        report += compare(drawing, args.reference).text()
    (out / "report.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nРезультаты: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
