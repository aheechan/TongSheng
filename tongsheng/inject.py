"""Paste text into the focused window (optional convenience)."""

from __future__ import annotations

import ctypes
import time

from .logs import get_logger

log = get_logger("inject")

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def copy_to_clipboard(text: str) -> bool:
    if not text:
        return False
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        log.warning("OpenClipboard failed")
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _press_vk(vk: int, up: bool = False) -> None:
    flags = KEYEVENTF_KEYUP if up else 0
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


def paste_text(text: str, delay_ms: int = 60) -> bool:
    """Copy then synthesize Ctrl+V — works in most editors and chat boxes."""
    if not copy_to_clipboard(text):
        return False
    time.sleep(max(0, delay_ms) / 1000.0)
    _press_vk(VK_CONTROL)
    _press_vk(VK_V)
    _press_vk(VK_V, up=True)
    _press_vk(VK_CONTROL, up=True)
    return True


__all__ = ["copy_to_clipboard", "paste_text"]
