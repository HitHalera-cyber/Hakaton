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

# the colours of the waiting screen's dawn: a deep violet room, the sun's orange
DAWN = {
    "ground": "#0E0B24",
    "card": "#171339",
    "card_alt": "#211B4C",
    "border": "#2E2766",
    "text": "#F2E9FF",
    "muted": "#A39BCB",
    "select": "#FF9A5C",
    "select_soft": "#3A2348",
    "action": "#FF8A52",
    "action_hover": "#FFA36F",
    "action_text": "#1A0E22",
    "ok": "#7FE2A8",
    "ok_soft": "#1C3030",
    "warn": "#FFC46E",
    "warn_soft": "#3A2A22",
    "sheet": "#120E2E",
    "grid": "#1D1846",
    "log": "#0A0820",
    "log_text": "#E2D8F6",
}

# warm paper of a drawing office: the «Мастер» look's own, good for any layout
PAPER = {
    "ground": "#F6F4EF",
    "card": "#FFFFFF",
    "card_alt": "#EEEBE4",
    "border": "#E2DED5",
    "text": "#1F2328",
    "muted": "#5F6670",
    "select": "#2457C5",
    "select_soft": "#E6ECF8",
    "action": "#2457C5",
    "action_hover": "#1A3F8F",
    "action_text": "#FFFFFF",
    "ok": "#2E7D4F",
    "ok_soft": "#E5F2E9",
    "warn": "#B45309",
    "warn_soft": "#FFF4E5",
    "sheet": "#FBFAF7",
    "grid": "#EEEBE4",
    "log": "#1F2328",
    "log_text": "#D9DDE3",
}

THEMES = {"light": LIGHT, "paper": PAPER, "dark": DARK, "dawn": DAWN}
THEME_NAMES = {"light": "Светлая тема", "paper": "Тема «Бумага»", "dark": "Тёмная тема",
               "dawn": "Тема «Рассвет»"}
THEME_ICONS = {"light": "☀", "paper": "▤", "dark": "☾", "dawn": "◐"}

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

/* the three layouts (layouts.py) */
#topbar {{ background: {c['log']}; border: none; }}
#topbar QLabel {{ color: {c['log_text']}; }}
#topBrand {{ font-size: 15px; font-weight: 700; letter-spacing: 0.5px; margin-right: 10px; }}
#topTitle {{ font-size: 15px; font-weight: 600; }}
#topbar QPushButton#secondary, #topbar QPushButton#flat {{ background: transparent;
    color: {c['log_text']}; border: 1px solid #45526E; min-height: 34px; }}
#topbar QPushButton#secondary:hover, #topbar QPushButton#flat:hover {{ border-color: {c['select']}; }}
#topbar #chip {{ background: #2A3550; color: {c['log_text']}; }}
#topbar QComboBox {{ background: transparent; color: {c['log_text']}; border-color: #45526E; }}
#footbar {{ background: {c['card']}; border-top: 1px solid {c['border']}; }}
#panel {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#section {{ color: {c['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
#mono {{ font-family: {MONO}; color: {c['muted']}; font-size: 12px; }}
#cardHead {{ font-size: 16px; font-weight: 700; }}
#question {{ background: {c['warn_soft']}; border: 1px solid {c['warn']}; border-radius: 12px; }}
#questionFlat {{ background: {c['card_alt']}; border: none; border-radius: 10px; }}
#questionTitle {{ font-weight: 600; }}
QPushButton#issue {{ text-align: left; min-height: 30px; padding: 4px 10px; border: none;
                     border-radius: 8px; background: {c['card_alt']}; font-size: 12px; }}
QPushButton#issue:hover {{ background: {c['warn_soft']}; color: {c['warn']}; }}
#step {{ background: {c['card']}; border: 1px dashed {c['border']}; border-radius: 12px; }}
#stepDone {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#stepNow {{ background: {c['select_soft']}; border: 2px solid {c['select']}; border-radius: 12px; }}
#stepTitle {{ font-weight: 700; }}
#stepBadge {{ border: 2px solid {c['border']}; border-radius: 15px; color: {c['muted']};
              font-weight: 700; }}
#stepBadgeDone {{ background: {c['ok']}; border-radius: 15px; color: {c['card']}; font-weight: 700; }}
#stepBadgeNow {{ background: {c['select']}; border-radius: 15px; color: {c['card']}; font-weight: 700; }}
QPushButton#seg {{ min-height: 32px; min-width: 70px; border: none; border-radius: 9px;
                   background: {c['card_alt']}; color: {c['muted']}; }}
QPushButton#seg:checked {{ background: {c['card']}; color: {c['text']}; font-weight: 700;
                           border: 1px solid {c['border']}; }}
#mini {{ background: {c['card_alt']}; border-radius: 10px; }}
#miniValue {{ font-size: 22px; font-weight: 700; }}
#rail {{ background: {c['card']}; border: none; border-right: 1px solid {c['border']}; }}
QPushButton#tile {{ text-align: left; padding: 14px 16px; border: 1px solid {c['border']};
                    border-radius: 16px; background: {c['card']}; font-size: 15px; font-weight: 600; }}
QPushButton#tile:hover {{ border-color: {c['select']}; background: {c['select_soft']}; }}
QPushButton#thumbCard {{ border: 1px solid {c['border']}; border-radius: 16px; background: {c['card']};
                         padding: 0; text-align: left; }}
QPushButton#thumbCard:hover {{ border-color: {c['select']}; }}
#clear {{ background: transparent; }}
QPushButton#small {{ min-height: 30px; min-width: 0; padding: 0 12px; border-radius: 8px;
                     border: 1px solid {c['border']}; background: {c['card']}; font-size: 13px;
                     font-weight: 600; }}
QPushButton#small:hover {{ border-color: {c['select']}; color: {c['select']}; }}
QPushButton#link {{ min-height: 24px; min-width: 0; padding: 0 4px; border: none;
                    background: transparent; color: {c['select']}; font-size: 13px; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QPushButton#icon {{ min-width: 36px; padding: 0 8px; border: none; border-radius: 10px;
                    background: transparent; color: {c['muted']}; font-size: 18px; }}
QPushButton#icon:hover {{ background: {c['card_alt']}; color: {c['text']}; }}
#tile {{ border: 1px solid {c['border']}; border-radius: 16px; background: {c['card']}; }}
#tile:hover {{ border-color: {c['select']}; background: {c['select_soft']}; }}
#tile:disabled {{ background: {c['card_alt']}; }}
#tileTitle {{ font-size: 15px; font-weight: 700; }}
#thumbCard {{ border: 1px solid {c['border']}; border-radius: 16px; background: {c['card']}; }}
#thumbCard:hover {{ border-color: {c['select']}; }}
#thumb {{ background: {c['sheet']}; border-top-left-radius: 16px; border-top-right-radius: 16px; }}
#thumbName {{ font-weight: 700; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ padding: 8px 16px; margin-right: 4px; border: none; border-radius: 10px;
                background: transparent; color: {c['muted']}; }}
QTabBar::tab:selected {{ background: {c['card']}; color: {c['text']}; font-weight: 700; }}
QTabBar::tab:hover {{ color: {c['text']}; }}
QTableWidget {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px;
                gridline-color: {c['border']}; selection-background-color: {c['select_soft']};
                selection-color: {c['select']}; }}
QHeaderView::section {{ background: {c['card_alt']}; color: {c['muted']}; border: none;
                        padding: 6px 8px; font-weight: 600; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['select_soft']}; color: {c['select']}; }}

QScrollBar:vertical, QScrollBar:horizontal {{ background: transparent; border: none;
                                             width: 10px; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {c['border']}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""
