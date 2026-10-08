# PyInstaller spec: one-folder Windows build of the KOMPAS-AI window.
#   cd kompas_ai_plugin
#   pyinstaller packaging/KompasAI.spec --noconfirm
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent          # kompas_ai_plugin/
CORE = ROOT / "core"

hidden = collect_submodules("kompas_ai")
if sys.platform == "win32":
    hidden += ["win32com", "win32com.client", "win32com.client.gencache", "pythoncom",
               "pywintypes", "win32timezone", "winreg"]

a = Analysis(
    [str(ROOT / "packaging" / "kompas_ai_app.py")],
    pathex=[str(CORE)],
    datas=collect_data_files("ezdxf") + [(str(ROOT / "packaging" / "icon" / "kompas_ai.png"), "kompas_ai")],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "PIL", "pytest", "IPython",
              # Qt parts the window does not use
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtNetwork", "PySide6.QtPdf",
              "PySide6.QtOpenGL", "PySide6.QtSvg", "PySide6.QtVirtualKeyboard",
              "PySide6.QtWebEngineCore", "PySide6.QtMultimedia", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="KompasAI",
    console=False,            # a window application, no black console
    icon=str(ROOT / "packaging" / "icon" / "kompas_ai.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="KompasAI")
