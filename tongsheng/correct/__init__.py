"""ASR error correction (context aware, meaning preserving).

Prompt design is adapted from ALT-VoiceType (Apache-2.0): the corrector may
only repair recognition errors, never rewrite the speaker.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..llm.client import ChatClient, LLMError

SYSTEM_PROMPT_ZH = """你是中文语音转写校对器。你的任务不是润色，而是修正语音识别错误。

只允许修改：
1. 同音字、近音字、错别字；
2. 明显的断句和标点错误；
3. 重复词、口吃、无意义语气词；
4. 人名、地名、产品名、术语的写法（优先使用【术语表】）；
5. 中英文混说时的明显识别错误。

严禁：改变原意、增加信息、扩写缩写、总结解释、改变语气、把口语改成书面语。

数字规则：数量、金额、年份、日期、时间、电话、编号统一写成阿拉伯数字。

如果无法确定，保留原文。输出必须是合法 JSON：
{"text": "校对后的文本", "risk": 0.0, "edits": [{"from": "错", "to": "对", "reason": "同音字"}]}
risk 取 0 到 1；不确定时给高风险。"""

SYSTEM_PROMPT_EN = """You are an English speech-to-text proofreader. Fix only ASR errors: spelling, homophones, punctuation, names, and terminology. Preserve the speaker's meaning, tone, and wording. Do not summarize or rewrite. All numbers must use Arabic digits. Output valid JSON: {"text": "corrected text", "risk": 0.0, "edits": [{"from": "wrong", "to": "right", "reason": "spelling"}]}. Return the original text when unsure."""


@dataclass
class CorrectionResult:
    text: str
    risk: float = 0.0
    edits: list[dict[str, Any]] = field(default_factory=list)
    applied: bool = False
    parse_error: bool = False


class Corrector:
    def __init__(self, client: ChatClient, max_tokens: int = 512,
                 max_edit_ratio: float = 0.35) -> None:
        self.client = client
        self.max_tokens = int(max_tokens)
        self.max_edit_ratio = float(max_edit_ratio)

    def build_messages(self, text: str, language: str = "zh",
                       context: list[dict[str, str]] | None = None,
                       glossary: dict[str, str] | None = None,
                       scene: str = "daily") -> list[dict[str, str]]:
        system = SYSTEM_PROMPT_ZH if language == "zh" else SYSTEM_PROMPT_EN
        user = "\n\n".join([
            f"场景：{scene}",
            f"【最近上下文】\n{_format_context(context)}",
            f"【术语表】\n{_format_glossary(glossary)}",
            f"【当前 ASR 原文】\n{text}",
            "请只修正识别错误，输出 JSON。",
        ])
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    def correct(self, text: str, language: str = "zh",
                context: list[dict[str, str]] | None = None,
                glossary: dict[str, str] | None = None,
                scene: str = "daily") -> CorrectionResult:
        source = (text or "").strip()
        if not source:
            return CorrectionResult(text="")
        try:
            response = self.client.chat(
                self.build_messages(source, language, context, glossary, scene),
                temperature=0.0, max_tokens=self.max_tokens, retries=1)
        except LLMError:
            return CorrectionResult(text=source, risk=1.0)
        return apply_guard(parse_correction(response, source), source,
                           self.max_edit_ratio)


class NullCorrector:
    def correct(self, text: str, **_kwargs: Any) -> CorrectionResult:
        return CorrectionResult(text=(text or "").strip())


def parse_correction(response: str, original: str) -> CorrectionResult:
    raw = (response or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if fenced:
        raw = fenced.group(1).strip()
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        return CorrectionResult(text=original, risk=1.0, parse_error=True)
    text = str(data.get("text") or data.get("corrected") or original).strip()
    try:
        risk = float(data.get("risk", 0.0))
    except (TypeError, ValueError):
        risk = 1.0
    edits = data.get("edits") if isinstance(data.get("edits"), list) else []
    return CorrectionResult(text=text or original,
                            risk=max(0.0, min(1.0, risk)),
                            edits=[e for e in edits if isinstance(e, dict)])


def apply_guard(result: CorrectionResult, original: str, max_ratio: float) -> CorrectionResult:
    """Reject corrections that rewrite too much of the sentence."""
    candidate = result.text.strip()
    if not candidate:
        result.text = original
        return result
    if result.risk > 0.9:
        result.text = original
        return result
    ratio = _edit_ratio(original, candidate)
    if ratio > max_ratio:
        result.text = original
        return result
    result.text = candidate
    result.applied = ratio > 0.0
    return result


def _edit_ratio(a: str, b: str) -> float:
    import difflib

    if not a or not b:
        return 1.0
    return 1.0 - difflib.SequenceMatcher(None, a, b).ratio()


def _format_context(context: list[dict[str, str]] | None) -> str:
    if not context:
        return "（无）"
    lines: list[str] = []
    for item in context[-4:]:
        corrected = (item.get("corrected") or "").strip()
        if corrected:
            lines.append(f"- {corrected}")
    return "\n".join(lines) if lines else "（无）"


def _format_glossary(glossary: dict[str, str] | None) -> str:
    if not glossary:
        return "（无）"
    return "\n".join(f"- {k} -> {v}" for k, v in list(glossary.items())[:60])


__all__ = ["Corrector", "NullCorrector", "CorrectionResult",
           "parse_correction", "apply_guard"]
