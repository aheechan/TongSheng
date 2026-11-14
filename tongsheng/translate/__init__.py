"""Natural spoken translation (Index-Translate via a local server).

Prompt design is adapted from ALT-VoiceType (Apache-2.0): interpret speech,
do not translate a document.
"""

from __future__ import annotations

import re
from typing import Any

from ..config import (LANGUAGE_NAMES_EN, normalize_language,
                      normalize_language_output, output_language_prompt_name)
from ..llm.client import ChatClient, LLMError

SYSTEM_PROMPT_ZH = """你是口译员，不是在翻译文件。把用户的口语翻成目标语言，只输出译文本身。
不要输出原文、标题、标签、解释、引号或 Markdown。译文要自然、口语化，保留情绪、语气和停顿。
数字统一保留阿拉伯数字，例如 20、3.5、30%。"""

SYSTEM_PROMPT_EN = """You are an interpreter, not a document translator. Translate the user's speech into the target language. Output only the translation: no source label, heading, explanation, quotes, or Markdown. Keep numbers as Arabic digits. Preserve tone, emotion and meaning."""

STYLE_PRESETS: dict[str, dict[str, str]] = {
    "daily": {
        "zh": "日常口语。像朋友聊天一样自然，保留语气词、停顿和情绪；不要书面腔，不要翻译腔，不要总结。",
        "en": "Everyday speech. Natural like friends talking; keep fillers, pauses and emotion. No written style, no translationese, no summary.",
    },
    "live": {
        "zh": "直播/短视频口播。句子短、节奏快、有能量，保留主播的语气和互动感。",
        "en": "Live stream delivery. Short sentences, fast rhythm, energetic; keep the host's tone.",
    },
    "business": {
        "zh": "商务沟通。礼貌、清楚、简洁，但不僵硬；不要堆砌套话。",
        "en": "Business communication. Polite, clear, concise but not stiff; avoid boilerplate.",
    },
    "subtitle": {
        "zh": "字幕。表达清楚、可读性优先，长度尽量紧凑。",
        "en": "Subtitles. Clear and readable, keep it compact.",
    },
}


class TranslationError(RuntimeError):
    pass


class Translator:
    def __init__(self, client: ChatClient, max_tokens: int = 384,
                 style: str = "daily") -> None:
        self.client = client
        self.max_tokens = int(max_tokens)
        self.style = style

    def build_messages(self, text: str, target_lang: str, source_lang: str = "zh",
                       context: list[dict[str, str]] | None = None,
                       glossary: dict[str, str] | None = None) -> list[dict[str, str]]:
        style_map = STYLE_PRESETS.get(self.style, STYLE_PRESETS["daily"])
        style_text = style_map.get(source_lang, style_map["zh"])
        target = output_language_prompt_name(normalize_language_output(target_lang)) \
            or target_lang
        parts = [f"目标语言 / Target language：{target}", f"风格 / Style：{style_text}"]
        if glossary:
            parts.append("术语 / Glossary：\n" + "\n".join(
                f"{k} => {v}" for k, v in list(glossary.items())[:60]))
        if context:
            lines = []
            for item in context[-2:]:
                src = (item.get("corrected") or item.get("source") or "").strip()
                dst = (item.get("translation") or "").strip()
                if src and dst:
                    lines.append(f"{src} => {dst}")
            if lines:
                parts.append("上文 / Context：\n" + "\n".join(lines))
        parts.append(f"原文 / Source：\n{text}")
        parts.append("只输出译文，不要输出“原文”或“译文”标题。")
        system = SYSTEM_PROMPT_ZH if source_lang == "zh" else SYSTEM_PROMPT_EN
        return [{"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(parts)}]

    def translate(self, text: str, target_lang: str, source_lang: str = "zh",
                  context: list[dict[str, str]] | None = None,
                  glossary: dict[str, str] | None = None) -> str:
        source = (text or "").strip()
        if not source:
            return ""
        target = normalize_language_output(target_lang) or normalize_language(target_lang)
        if target == normalize_language(source_lang):
            return source
        messages = self.build_messages(source, target, source_lang, context, glossary)
        try:
            response = self.client.chat(
                messages, temperature=0.0, max_tokens=self.max_tokens, retries=1,
                stop=["\n原文", "\n译文", "\nTranslation:", "\nSource:"])
        except LLMError as exc:
            raise TranslationError(f"翻译服务不可用：{exc}") from exc
        result = clean_translation(response)
        if not result:
            raise TranslationError("翻译模型返回了空结果")
        return result


class NullTranslator:
    def translate(self, text: str, target_lang: str = "en", **_kwargs: Any) -> str:
        return (text or "").strip()


def clean_translation(text: str) -> str:
    result = (text or "").strip()
    if result.startswith("```") and result.endswith("```"):
        lines = result.splitlines()
        if len(lines) >= 3:
            result = "\n".join(lines[1:-1]).strip()
    for marker in ("译文：", "译文:", "Translation:", "翻译：", "Output:"):
        if marker in result:
            result = result.rsplit(marker, 1)[-1].strip()
    result = re.sub(
        r"^\s*(?:\*\*)?\s*(?:原文|译文|翻译|Translation|Source|Target|Output)\s*[:：]\s*(?:\*\*)?\s*",
        "", result, flags=re.IGNORECASE)
    result = re.sub(r"</?(?:source|target|context|glossary)>", "", result,
                    flags=re.IGNORECASE)
    return result.strip().strip("*").strip('"').strip("“”").strip()


__all__ = ["Translator", "NullTranslator", "TranslationError",
           "clean_translation", "STYLE_PRESETS"]
