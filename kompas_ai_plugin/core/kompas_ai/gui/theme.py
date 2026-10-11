"""Light and dark look of the window: one style sheet, two palettes.

Layout of cards on a calm ground; colours of a CAD program — white sheets on
grey (light) or graphite (dark), blue for selection, green for the main action.
"""

from __future__ import annotations

LIGHT = {
    "ground": "#F4F6F9",
    "card": "#FFFFFF",
    "card_alt": "#EEF2F7",
    "border": "#DCE2EA",
    "text": "#18222F",
    "muted": "#5A6778",
    "select": "#1F5FAD",
    "select_soft": "#E8F0FA",
    "action": "#2E9E5B",
    "action_hover": "#278A4F",
    "action_text": "#FFFFFF",
    "ok": "#1C6B3A",
    "ok_soft": "#E7F5EC",
    "warn": "#B45309",
    "warn_soft": "#FDF0E1",
    "sheet": "#FFFFFF",
    "grid": "#EEF2F7",
    "log": "#0F1722",
    "log_text": "#CFD8E3",
}

DARK = {
    "ground": "#17181A",
    "card": "#232528",
    "card_alt": "#2B2E33",
    "border": "#303338",
    "text": "#E3E5E8",
    "muted": "#8C9199",
    "select": "#6FB1EE",
    "select_soft": "#2F3D52",
    "action": "#5FD38A",
    "action_hover": "#78DE9E",
    "action_text": "#0C1A10",
    "ok": "#7FE2A8",
    "ok_soft": "#1F3328",
    "warn": "#F0B35C",
    "warn_soft": "#3A2E1C",
    "sheet": "#1A1B1D",
    "grid": "#25272B",
    "log": "#111214",
    "log_text": "#CFD8E3",
}

THEMES = {"light": LIGHT, "dark": DARK}

CHECK_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
             '<path d="M4.5 9.5l3 3 6-7" fill="none" stroke="{color}" stroke-width="2.2" '
             'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def check_icon(color: str) -> str:
    """A tick for the check boxes, written once per colour; style sheets need a file."""
    import tempfile
    from pathlib import Path

    path = Path(tempfile.gettempdir()) / f"kompas_ai_check_{color.lstrip('#')}.svg"
    if not path.exists():
        path.write_text(CHECK_SVG.format(color=color), encoding="utf-8")
    return path.as_posix()

FONT = '"Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", sans-serif'
MONO = '"Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", monospace'


def style_sheet(c: dict[str, str]) -> str:
    return f"""
* {{ font-family: {FONT}; font-size: 14px; color: {c['text']}; }}
QMainWindow, #root {{ background: {c['ground']}; }}
QStatusBar {{ background: {c['ground']}; color: {c['muted']}; font-size: 12px; }}
QStatusBar QLabel {{ color: {c['muted']}; font-size: 12px; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 6px; }}

#card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 18px; }}
#cardAccent {{ background: {c['card_alt']}; border: 1px solid {c['border']}; border-radius: 18px; }}
#sidebar {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 20px; }}
#brand {{ font-size: 16px; font-weight: 700; letter-spacing: 0.5px; }}
#title {{ font-size: 26px; font-weight: 700; }}
#cardTitle {{ color: {c['muted']}; font-size: 13px; }}
#big {{ font-size: 40px; font-weight: 700; }}
#sub {{ color: {c['muted']}; font-size: 13px; }}
#subOk {{ color: {c['ok']}; font-size: 13px; }}
#subWarn {{ color: {c['warn']}; font-size: 13px; }}
#chip {{ background: {c['select_soft']}; color: {c['select']}; border-radius: 11px;
         padding: 4px 12px; font-size: 12px; font-weight: 600; }}
#chipOk {{ background: {c['ok_soft']}; color: {c['ok']}; border-radius: 11px;
           padding: 4px 12px; font-size: 12px; font-weight: 600; }}
#chipWarn {{ background: {c['warn_soft']}; color: {c['warn']}; border-radius: 11px;
             padding: 4px 12px; font-size: 12px; font-weight: 600; }}
#kompas {{ background: {c['card_alt']}; border-radius: 14px; padding: 12px 14px;
           color: {c['muted']}; font-size: 13px; }}

QDialog, QMessageBox {{ background: {c['card']}; }}
QMessageBox QLabel {{ color: {c['text']}; font-size: 14px; }}
QPushButton {{ min-height: 34px; min-width: 88px; padding: 0 16px; border: 1px solid {c['border']};
               border-radius: 10px; background: {c['card_alt']}; color: {c['text']}; }}
QPushButton:hover {{ border-color: {c['select']}; }}

QPushButton#nav {{ text-align: left; padding: 0 14px; min-height: 42px; border: none;
                   border-radius: 12px; background: transparent; color: {c['muted']}; }}
QPushButton#nav:hover {{ background: {c['card_alt']}; color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['select_soft']}; color: {c['select']}; font-weight: 600; }}

QPushButton#primary {{ min-height: 44px; padding: 0 22px; border: none; border-radius: 14px;
                       background: {c['action']}; color: {c['action_text']};
                       font-size: 15px; font-weight: 700; }}
QPushButton#primary:hover {{ background: {c['action_hover']}; }}
QPushButton#primary:disabled {{ background: {c['card_alt']}; color: {c['muted']}; }}
QPushButton#secondary {{ min-height: 40px; padding: 0 18px; border: 1px solid {c['border']};
                         border-radius: 12px; background: {c['card']}; font-weight: 600; }}
QPushButton#secondary:hover {{ border-color: {c['select']}; color: {c['select']}; }}
QPushButton#secondary:disabled {{ color: {c['muted']}; }}
QPushButton#flat {{ min-height: 36px; padding: 0 12px; border: none; border-radius: 10px;
                    background: transparent; color: {c['muted']}; text-align: left; }}
QPushButton#flat:hover {{ background: {c['card_alt']}; color: {c['text']}; }}

QComboBox {{ min-height: 36px; padding: 0 12px; border: 1px solid {c['border']}; border-radius: 10px;
             background: {c['card']}; }}
QComboBox:hover {{ border-color: {c['select']}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
                               selection-background-color: {c['select_soft']};
                               selection-color: {c['select']}; outline: none; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
                        border: 1px solid {c['border']}; background: {c['card']}; }}
QCheckBox::indicator:checked {{ background: {c['select']}; border-color: {c['select']};
                                image: url({check_icon(c['card'])}); }}

QPlainTextEdit, QListWidget {{ background: {c['card']}; border: none; border-radius: 12px;
                               padding: 6px; selection-background-color: {c['select_soft']};
                               selection-color: {c['select']}; }}
QPlainTextEdit#log {{ background: {c['log']}; color: {c['log_text']}; font-family: {MONO};
                      font-size: 12px; padding: 10px 14px; }}
QPlainTextEdit#report {{ font-family: {MONO}; font-size: 12px; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; }}
QListWidget::item:hover {{ background: {c['card_alt']}; }}
QListWidget::item:selected {{ background: {c['select_soft']}; color: {c['select']}; }}
QGraphicsView {{ border: none; border-radius: 12px; }}

QScrollBar:vertical, QScrollBar:horizontal {{ background: transparent; border: none;
                                             width: 10px; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {c['border']}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""
