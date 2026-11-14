"""Global push-to-talk hotkey (Windows low level keyboard hook).

Runs its own thread with a Win32 message loop; delivers press/release events as
plain callbacks so the rest of the app stays free of Win32 details.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import threading
from dataclasses import dataclass, field
from typing import Callable

from .logs import get_logger

log = get_logger("hotkey")

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
LLKHF_INJECTED = 0x10

MODIFIERS = {
    "ctrl": {0xA2, 0xA3},      # left / right control
    "alt": {0xA4, 0xA5},       # left / right alt
    "shift": {0xA0, 0xA1},
    "win": {0x5B, 0x5C},
}

VK_NAMES = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "capslock": 0x14, "`:": 0xC0, "~": 0xC0,
    # side-specific modifiers, usable as the main key (project B style)
    "lalt": 0xA4, "ralt": 0xA5, "lctrl": 0xA2, "rctrl": 0xA3,
    "lshift": 0xA0, "rshift": 0xA1,
}
for _i in range(1, 25):
    VK_NAMES[f"f{_i}"] = 0x6F + _i
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK_NAMES[_c] = ord(_c.upper())
for _c in "0123456789":
    VK_NAMES[_c] = ord(_c)


def normalise_vk(vk: int, flags: int) -> int:
    """Map generic modifier VKs to left/right specific ones."""
    extended = bool(flags & 0x01)  # LLKHF_EXTENDED
    if vk == 0x12:
        return 0xA5 if extended else 0xA4
    if vk == 0x11:
        return 0xA3 if extended else 0xA2
    if vk == 0x10:
        return 0xA1 if extended else 0xA0
    return vk


@dataclass
class Combo:
    modifiers: set[str] = field(default_factory=set)
    key: int | None = None
    text: str = ""

    @property
    def modifier_vks(self) -> set[int]:
        vks: set[int] = set()
        for name in self.modifiers:
            vks |= MODIFIERS[name]
        return vks

    def pressed(self, down: set[int]) -> bool:
        for name in self.modifiers:
            if not (MODIFIERS[name] & down):
                return False
        if self.key is not None and self.key not in down:
            return False
        return True


def parse_combo(text: str) -> Combo:
    raw = (text or "").strip().lower().replace(" ", "")
    if not raw:
        raw = "lalt"
    parts = [p for p in raw.split("+") if p]
    combo = Combo(text="+".join(parts))
    for part in parts:
        if part in MODIFIERS:
            combo.modifiers.add(part)
            continue
        if part in VK_NAMES:
            combo.key = VK_NAMES[part]
            continue
        if len(part) == 1:
            combo.key = ord(part.upper())
            continue
        raise ValueError(f"无法识别的按键：{part}")
    if not combo.modifiers and combo.key is None:
        raise ValueError("快捷键不能为空")
    return combo


class HotkeyListener:
    """WH_KEYBOARD_LL based listener supporting hold-style push to talk."""

    def __init__(self, combo: str = "ctrl+alt",
                 on_press: Callable[[], None] | None = None,
                 on_release: Callable[[], None] | None = None) -> None:
        self.combo = parse_combo(combo)
        self.on_press = on_press or (lambda: None)
        self.on_release = on_release or (lambda: None)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._thread_id = 0
        self._down: set[int] = set()
        self._active = False
        self._hook = None

    # -- state machine --------------------------------------------------
    def _is_pressed(self) -> bool:
        return self.combo.pressed(self._down)

    def _handle(self, vk: int, is_down: bool) -> None:
        if is_down:
            self._down.add(vk)
        else:
            self._down.discard(vk)
        pressed = self._is_pressed()
        if pressed and not self._active:
            self._active = True
            try:
                self.on_press()
            except Exception:
                log.exception("press callback failed")
        elif not pressed and self._active:
            self._active = False
            try:
                self.on_release()
            except Exception:
                log.exception("release callback failed")

    # -- hook -----------------------------------------------------------
    def start(self) -> bool:
        if self._thread is not None:
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ts-hotkey", daemon=True)
        self._thread.start()
        for _ in range(50):
            if self._thread_id:
                return True
            threading.Event().wait(0.02)
        return bool(self._thread_id)

    def stop(self) -> None:
        self._stop.set()
        thread_id = self._thread_id
        if thread_id:
            ctypes.windll.user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)  # WM_QUIT
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.5)
        self._thread = None
        self._thread_id = 0

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int,
                                      wintypes.WPARAM, wintypes.LPARAM)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

        def callback(n_code, w_param, l_param):  # noqa: ANN001
            if n_code == 0:
                data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (data.flags & LLKHF_INJECTED):
                    vk = normalise_vk(int(data.vkCode), int(data.flags))
                    if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        self._handle(vk, True)
                    elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                        self._handle(vk, False)
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(callback)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self._hook:
            log.error("SetWindowsHookExW failed: %s", ctypes.get_last_error())
            self._thread_id = 0
            return
        log.info("hotkey hook installed (%s)", self.combo.text)
        msg = wintypes.MSG()
        while not self._stop.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        self._thread_id = 0


__all__ = ["HotkeyListener", "Combo", "parse_combo"]
