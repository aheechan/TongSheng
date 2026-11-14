"""Paste the translated text at the caret (dialogs, chat boxes, web inputs).

Two-step clipboard hand-off: put the text on the clipboard, synthesise Ctrl+V,
then restore whatever the user had copied before so nothing is lost.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import time

from .logs import get_logger

log = get_logger("inject")

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
ULONG_PTR = ctypes.c_size_t

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

# 64-bit safety: without these prototypes the handle is truncated to 32 bits.
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
_user32.GetClipboardData.restype = ctypes.c_void_p
_user32.GetClipboardData.argtypes = [wintypes.UINT]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def _send_vk(vk: int, up: bool = False) -> None:
    flags = KEYEVENTF_KEYUP if up else 0
    event = INPUT(type=INPUT_KEYBOARD,
                  union=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags,
                                                  time=0, dwExtraInfo=0)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))


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


def _read_clipboard_text() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(pointer) if pointer else ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def paste_text(text: str, delay_ms: int = 40, restore_clipboard: bool = True) -> bool:
    """Put ``text`` on the clipboard and press Ctrl+V in the focused window."""
    if not text:
        return False
    previous = _read_clipboard_text() if restore_clipboard else ""
    if not copy_to_clipboard(text):
        return False
    time.sleep(max(0, delay_ms) / 1000.0)
    _send_vk(0x11)          # Ctrl down
    _send_vk(0x56)          # V down
    _send_vk(0x56, up=True)
    _send_vk(0x11, up=True)
    if restore_clipboard and previous and previous != text:
        # give the target app a moment to consume the paste before restoring
        time.sleep(max(0.08, delay_ms / 1000.0))
        copy_to_clipboard(previous)
    return True


__all__ = ["copy_to_clipboard", "paste_text"]
