"""Text helpers shared by the pipeline and the TTS runtime."""

from __future__ import annotations

import re

_CJK = re.compile(r"[\u4e00-\u9fff]")
_EN = re.compile(r"[A-Za-z]")

# sentence terminators for both languages
_END = "。！？!?；;…\n"
_SOFT = "，,、：: "


def detect_language(text: str) -> str:
    """'zh' when CJK dominates, otherwise 'en'."""
    if not text:
        return "zh"
    cjk = len(_CJK.findall(text))
    latin = len(_EN.findall(text))
    return "zh" if cjk >= latin else "en"


def split_sentences(text: str, max_chars: int = 50, lang: str = "zh",
                    min_chars: int = 0) -> list[str]:
    """Split into TTS-sized chunks without breaking words."""
    value = re.sub(r"\s+", " ", (text or "").strip())
    if not value:
        return []
    chunks: list[str] = []
    buffer = ""
    for char in value:
        buffer += char
        if char in _END and len(buffer.strip()) >= 2:
            chunks.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        chunks.append(buffer.strip())

    out: list[str] = []
    for chunk in chunks:
        out.extend(_split_long(chunk, max_chars, lang))
    out = [c for c in out if c.strip()]
    if min_chars > 1 and len(out) > 1:
        # project A never synthesises 1–2 character fragments: merge them into
        # the neighbouring sentence so prosody stays natural
        merged: list[str] = []
        pending = ""
        for piece in out:
            candidate = (pending + piece) if pending else piece
            if len(candidate) < min_chars:
                pending = candidate
                continue
            merged.append(candidate)
            pending = ""
        if pending:
            if merged:
                merged[-1] += pending
            else:
                merged.append(pending)
        out = merged
    return out


def _split_long(text: str, max_chars: int, lang: str) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    if lang == "zh":
        pieces: list[str] = []
        current = ""
        for char in text:
            current += char
            if char in _SOFT and len(current) >= max_chars * 0.6:
                pieces.append(current.strip())
                current = ""
        if current.strip():
            pieces.append(current.strip())
        result: list[str] = []
        for piece in pieces:
            while len(piece) > max_chars:
                result.append(piece[:max_chars])
                piece = piece[max_chars:]
            if piece:
                result.append(piece)
        return result

    words = text.split(" ")
    result = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            result.append(current)
            current = word
        else:
            current = candidate
    if current:
        result.append(current)
    return result


def strip_marks(text: str) -> str:
    return (text or "").strip().strip('"').strip("“”").strip()


__all__ = ["detect_language", "split_sentences", "strip_marks"]
