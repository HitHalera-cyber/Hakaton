"""Entry point of the packaged application (KompasAI.exe).

``KompasAI.exe --selftest report.txt`` checks the packaged libraries without
opening the window: it imports them, recognises a small generated drawing and
writes the result to the report (exit code 0 = everything works). The build
runs it so a broken package is caught before it is published.
"""

import sys


def selftest(report_path: str) -> int:
    import tempfile
    import traceback
    from pathlib import Path

    lines = []
    code = 0
    try:
        import numpy
        import shapely
        import pymupdf
        import ezdxf
        from PySide6 import QtCore

        lines.append(f"numpy {numpy.__version__}, shapely {shapely.__version__}, "
                     f"pymupdf {pymupdf.VersionBind}, ezdxf {ezdxf.__version__}, "
                     f"Qt {QtCore.qVersion()}")
        from kompas_ai import ir
        from kompas_ai.pipeline import recognize_pdf

        mm = 72 / 25.4
        pdf = Path(tempfile.mkdtemp()) / "selftest.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=210 * mm, height=297 * mm)
        for a, b in (((40, 100), (140, 100)), ((140, 100), (140, 160)),
                     ((140, 160), (40, 160)), ((40, 160), (40, 100))):
            page.draw_line((a[0] * mm, a[1] * mm), (b[0] * mm, b[1] * mm), width=0.6 * mm)
        page.draw_circle((90 * mm, 130 * mm), 15 * mm, width=0.6 * mm)
        doc.save(str(pdf))
        doc.close()
        drawing = recognize_pdf(pdf)
        lines.append(f"распознано: линий {len(drawing.of_type(ir.Line))}, "
                     f"окружностей {len(drawing.of_type(ir.Circle))}")
        if len(drawing.of_type(ir.Circle)) != 1 or len(drawing.of_type(ir.Line)) != 4:
            raise RuntimeError("распознавание тестового чертежа дало неверный результат")
        if sys.platform == "win32":
            # COM wrappers generated and imported in the exe as for KOMPAS (Microsoft
            # Scripting Runtime: on every Windows): «No module named win32com.gen_py…»
            from kompas_ai.kompas.api5 import _prepare_win32com, ensure_wrapper

            _prepare_win32com()
            m = ensure_wrapper("{420B2830-E718-11CF-893D-00A0C9054228}", 1, 0)
            if m is None or not hasattr(m, "CLSIDToClassMap"):
                raise RuntimeError("обёртка COM не создана")
            lines.append(f"COM: {m.__name__}")
        lines.append("OK")
    except BaseException:
        lines.append(traceback.format_exc())
        code = 1
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(selftest(sys.argv[2]))
    from kompas_ai.gui.app import main

    sys.exit(main())
