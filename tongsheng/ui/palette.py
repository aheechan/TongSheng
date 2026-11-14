"""Dark palette shared by the control window (matches the TS-mic mark)."""

from __future__ import annotations

BG = "#0A1420"
PANEL = "#101D2C"
PANEL_HI = "#16273A"
LINE = "#1E3348"
TEXT = "#E8F3FF"
MUTED = "#7E96AD"
CYAN = "#7AF5FF"
BLUE = "#35C5FF"
ACCENT = "#2F8DFF"
ERROR = "#FF6B6B"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QLabel#title {{
    font-size: 20px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#subtitle {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#rowlabel {{
    color: {MUTED};
}}
QLabel#hint {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#state {{
    color: {MUTED};
    padding: 4px 10px;
    border: 1px solid {LINE};
    border-radius: 11px;
}}
QLabel#state[busy="true"] {{
    color: {CYAN};
    border-color: {ACCENT};
}}
QFrame#divider {{
    color: {LINE};
    background: {LINE};
    max-height: 1px;
    border: none;
}}
QPushButton {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: {PANEL_HI};
    border-color: {ACCENT};
}}
QPushButton:checked {{
    background: {PANEL_HI};
    border: 1px solid {ACCENT};
    color: {CYAN};
}}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {ACCENT}, stop:1 {BLUE});
    border: none;
    font-size: 15px;
    font-weight: 600;
    color: #04121F;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {BLUE}, stop:1 {CYAN});
}}
QComboBox {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox:hover {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {LINE};
    selection-background-color: {PANEL_HI};
    selection-color: {CYAN};
    outline: none;
}}
QTextEdit#transcript {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {LINE};
    border-radius: 4px;
    min-height: 24px;
}}
QMenu {{
    background: {PANEL};
    border: 1px solid {LINE};
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 22px 6px 18px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {PANEL_HI};
    color: {CYAN};
}}
"""

__all__ = ["STYLESHEET"]
