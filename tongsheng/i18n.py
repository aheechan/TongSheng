"""Bilingual UI strings (zh / en).

The tray language switch changes both the interface language and the speech
recognition language, so every user-visible string lives here.
"""

from __future__ import annotations

from typing import Callable

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # ---- app / tray ----------------------------------------------------
    "app.name": {"zh": "同声", "en": "TongSheng"},
    "app.desc": {"zh": "用你的声音，说任何语言", "en": "Your voice, any language"},
    "tray.tooltip.idle": {"zh": "同声 · 待机", "en": "TongSheng · idle"},
    "tray.tooltip.recording": {"zh": "同声 · 正在聆听…", "en": "TongSheng · listening…"},
    "tray.tooltip.busy": {"zh": "同声 · 处理中…", "en": "TongSheng · working…"},
    "tray.tooltip.speaking": {"zh": "同声 · 正在朗读", "en": "TongSheng · speaking"},

    # ---- menu ----------------------------------------------------------
    "menu.status": {"zh": "状态", "en": "Status"},
    "menu.mode": {"zh": "输出品质", "en": "Output quality"},
    "menu.language": {"zh": "输入语言", "en": "Input language"},
    "menu.output_language": {"zh": "输出语言", "en": "Output language"},
    "menu.text_only": {"zh": "仅文字", "en": "text only"},
    "menu.voice": {"zh": "音色", "en": "Voice"},
    "menu.start": {"zh": "开始说话", "en": "Start talking"},
    "menu.stop": {"zh": "停止", "en": "Stop"},
    "menu.settings": {"zh": "设置…", "en": "Settings…"},
    "menu.history": {"zh": "历史记录…", "en": "History…"},
    "menu.open_results": {"zh": "打开录音目录", "en": "Open recordings"},
    "menu.reload_voice": {"zh": "重新加载音色", "en": "Reload voice"},
    "menu.check": {"zh": "自检…", "en": "Diagnostics…"},
    "menu.open_window": {"zh": "打开主窗口", "en": "Open window"},
    "menu.warmup": {"zh": "模型预热", "en": "Warm up models"},
    "warmup.running": {"zh": "正在预热模型…", "en": "Warming up models…"},
    "warmup.done": {"zh": "模型已就绪，可以开始说话", "en": "Models are ready — start talking"},
    "warmup.failed": {"zh": "预热失败：{message}", "en": "Warm-up failed: {message}"},
    "meter.tooltip": {"zh": "麦克风输入电平（录音时实时显示）",
                      "en": "Microphone input level (live while recording)"},
    "menu.quit": {"zh": "退出", "en": "Quit"},
    "menu.about": {"zh": "关于同声", "en": "About TongSheng"},

    # ---- main window ---------------------------------------------------
    "window.transcript_empty": {
        "zh": "按住快捷键说完一句话，这里会显示识别、纠错与译文。",
        "en": "Hold the hotkey and speak — recognition, correction and translation show up here.",
    },
    "window.still_running": {
        "zh": "窗口已隐藏，程序仍在托盘运行。双击托盘图标可以再次打开。",
        "en": "Window hidden — still running in the tray. Double-click the tray icon to reopen.",
    },
    "window.still_running_title": {"zh": "同声仍在运行", "en": "TongSheng is still running"},

    # ---- states --------------------------------------------------------
    "state.idle": {"zh": "待机", "en": "Idle"},
    "state.listening": {"zh": "聆听中", "en": "Listening"},
    "state.asr": {"zh": "识别中", "en": "Recognizing"},
    "state.correct": {"zh": "纠错中", "en": "Correcting"},
    "state.translate": {"zh": "翻译中", "en": "Translating"},
    "state.speak": {"zh": "合成中", "en": "Synthesizing"},
    "state.playing": {"zh": "朗读中", "en": "Speaking"},
    "state.error": {"zh": "出错", "en": "Error"},
    "state.ready": {"zh": "就绪", "en": "Ready"},

    # ---- notifications -------------------------------------------------
    "notify.title": {"zh": "同声翻译", "en": "TongSheng"},
    "notify.copied": {"zh": "译文已复制到剪贴板", "en": "Translation copied"},
    "notify.saved": {"zh": "录音已保存：{path}", "en": "Saved: {path}"},
    "notify.no_speech": {"zh": "没有识别到语音", "en": "No speech detected"},
    "notify.no_voice": {"zh": "还没有可用音色，请先训练或导入一个", "en": "No voice yet — train or import one"},
    "notify.asr_warming": {"zh": "正在预热{lang}识别模型…", "en": "Warming up the {lang} recogniser…"},
    "notify.asr_ready": {"zh": "{lang}识别模型已就绪", "en": "{lang} recognition is ready"},
    "notify.asr_restart": {"zh": "{lang}识别模型加载失败，正在重启程序…",
                           "en": "Cannot load the {lang} recogniser — restarting TongSheng…"},
    "notify.text_only": {"zh": "「{lang}」暂不支持克隆音色合成，只输出文字译文",
                         "en": "{lang} has no cloned-voice synthesis yet — text only"},

    # ---- settings dialog ----------------------------------------------
    "settings.title": {"zh": "同声设置", "en": "TongSheng settings"},
    "settings.general": {"zh": "常规", "en": "General"},
    "settings.language": {"zh": "输入语言", "en": "Input language"},
    "settings.input_language": {"zh": "输入语言", "en": "Input language"},
    "settings.output_language": {"zh": "输出语言", "en": "Output language"},
    "settings.mode": {"zh": "输出品质", "en": "Output quality"},
    "settings.hotkey": {"zh": "快捷键", "en": "Hotkey"},
    "settings.hotkey_mode": {"zh": "触发方式", "en": "Trigger"},
    "settings.hotkey.smart": {"zh": "轻点锁定 / 长按说话", "en": "Tap to latch / hold to talk"},
    "settings.hotkey.hold": {"zh": "按住说话", "en": "Hold to talk"},
    "settings.hotkey.toggle": {"zh": "按一下开始 / 再按停止", "en": "Tap to start / stop"},
    "settings.emotion": {"zh": "默认情绪", "en": "Default emotion"},
    "settings.live_volume": {"zh": "LIVE 输出音量", "en": "LIVE output volume"},
    "settings.devices": {"zh": "音频设备", "en": "Audio devices"},
    "settings.input": {"zh": "麦克风", "en": "Microphone"},
    "settings.output": {"zh": "扬声器", "en": "Speaker"},
    "settings.default_device": {"zh": "系统默认", "en": "System default"},
    "settings.asr": {"zh": "语音识别", "en": "Speech recognition"},
    "settings.asr.zh": {"zh": "中文模型", "en": "Chinese engine"},
    "settings.asr.en": {"zh": "英文模型", "en": "English engine"},
    "settings.device": {"zh": "推理设备", "en": "Compute device"},
    "settings.tts": {"zh": "语音合成", "en": "Speech synthesis"},
    "settings.voice": {"zh": "音色", "en": "Voice"},
    "settings.speed": {"zh": "语速", "en": "Speed"},
    "settings.translate": {"zh": "翻译", "en": "Translation"},
    "settings.style": {"zh": "风格", "en": "Style"},
    "settings.target": {"zh": "目标语言", "en": "Target language"},
    "settings.inject": {"zh": "翻译后同时粘贴到当前窗口", "en": "Paste the translation into the focused app"},
    "settings.save": {"zh": "保存", "en": "Save"},
    "settings.cancel": {"zh": "取消", "en": "Cancel"},
    "settings.apply_restart": {"zh": "部分设置将在下次启动生效", "en": "Some changes apply on next start"},
    "settings.models_missing": {"zh": "未找到模型目录，请检查路径设置", "en": "Model folder not found — check the paths"},
    "settings.quality.live": {"zh": "低档 · LIVE · 24 kHz", "en": "Low tier · LIVE · 24 kHz"},
    "settings.quality.rec": {"zh": "高档 · REC · 48 kHz", "en": "High tier · REC · 48 kHz"},

    # ---- diagnostics ---------------------------------------------------
    "check.title": {"zh": "自检结果", "en": "Diagnostics"},
    "check.gpu": {"zh": "显卡", "en": "GPU"},
    "check.asr": {"zh": "识别引擎", "en": "ASR engine"},
    "check.tts": {"zh": "合成引擎", "en": "TTS engine"},
    "check.llm": {"zh": "语言模型服务", "en": "Language servers"},
    "check.voices": {"zh": "音色", "en": "Voices"},
    "check.ok": {"zh": "正常", "en": "OK"},
    "check.fail": {"zh": "不可用", "en": "Unavailable"},

    # ---- errors --------------------------------------------------------
    "error.generic": {"zh": "出错了：{message}", "en": "Error: {message}"},
    "error.asr": {"zh": "识别失败：{message}", "en": "Recognition failed: {message}"},
    "error.translate": {"zh": "翻译失败：{message}", "en": "Translation failed: {message}"},
    "error.tts": {"zh": "合成失败：{message}", "en": "Synthesis failed: {message}"},
    "error.llm_down": {"zh": "翻译服务未就绪，请查看 logs 目录", "en": "Translation service is not ready, see logs"},

    # ---- voice / training ---------------------------------------------
    "voice.none": {"zh": "（无）", "en": "(none)"},
    "voice.untrained": {"zh": "零样本（仅参考音频）", "en": "Zero-shot (reference only)"},
    "train.title": {"zh": "声音模型训练", "en": "Voice model training"},
    "train.tab.library": {"zh": "音色库", "en": "Voice library"},
    "train.tab.new": {"zh": "新建音色", "en": "New voice"},
    "train.name": {"zh": "音色名称", "en": "Voice name"},
    "train.name.ph": {"zh": "例如：我的声音", "en": "e.g. My voice"},
    "train.source": {"zh": "声音素材", "en": "Audio source"},
    "train.choose": {"zh": "选择音频…", "en": "Choose audio…"},
    "train.record": {"zh": "● 开始录制", "en": "● Record"},
    "train.record.stop": {"zh": "■ 停止录制", "en": "■ Stop"},
    "train.info.empty": {"zh": "还没有选择素材。建议 45 秒以上、安静环境的清晰人声。",
                         "en": "No audio yet. 45 s+ of clean speech in a quiet room works best."},
    "train.info.file": {"zh": "已选择：{name}（{secs:.1f} 秒 / {sr} Hz）",
                        "en": "Selected: {name} ({secs:.1f}s / {sr} Hz)"},
    "train.info.short": {"zh": "素材偏短（{secs:.1f} 秒），建议 45 秒以上才能学到稳定音色。",
                         "en": "Only {secs:.1f}s — 45 s+ gives a much more stable voice."},
    "train.start": {"zh": "开始训练", "en": "Start training"},
    "train.cancel": {"zh": "取消训练", "en": "Cancel"},
    "train.close": {"zh": "关闭", "en": "Close"},
    "train.log": {"zh": "训练日志", "en": "Training log"},
    "train.set_default": {"zh": "设为默认", "en": "Set default"},
    "train.delete": {"zh": "删除", "en": "Delete"},
    "train.open": {"zh": "打开目录", "en": "Open folder"},
    "train.use": {"zh": "使用", "en": "Use"},
    "train.empty": {"zh": "音色库还是空的，切到「新建音色」录一段就能开始。",
                    "en": "The library is empty — record a clip in “New voice” to start."},
    "train.delete.confirm": {"zh": "确定删除音色「{name}」？权重文件会被移除。",
                             "en": "Delete voice “{name}”? Its weights will be removed."},
    "train.need_name": {"zh": "先给这个音色起个名字", "en": "Give the voice a name first"},
    "train.need_audio": {"zh": "先选择或录制一段音频", "en": "Pick or record some audio first"},
    "train.running": {"zh": "训练中，可以继续用当前音色说话…", "en": "Training… the current voice keeps working"},
    "train.done": {"zh": "训练完成：{name}", "en": "Training finished: {name}"},
    "train.failed": {"zh": "训练失败：{message}", "en": "Training failed: {message}"},
    "train.recording": {"zh": "录制中… 再次点击停止", "en": "Recording… click again to stop"},
    "train.default_badge": {"zh": "默认", "en": "default"},
    "train.ready_badge": {"zh": "可用", "en": "ready"},
    "train.broken_badge": {"zh": "缺少文件", "en": "missing files"},
}

_language = "zh"
_listeners: list[Callable[[str], None]] = []


def language() -> str:
    return _language


def set_language(code: str) -> None:
    global _language
    code = "en" if str(code).lower().startswith("en") else "zh"
    if code == _language:
        return
    _language = code
    for callback in list(_listeners):
        try:
            callback(code)
        except Exception:
            pass


def on_language_change(callback: Callable[[str], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)


def t(key: str, **kwargs: object) -> str:
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        text = key
    else:
        text = entry.get(_language) or entry.get("zh") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def has(key: str) -> bool:
    return key in _TRANSLATIONS


def mode_label(mode: str) -> str:
    from .config import MODE_LABELS

    return MODE_LABELS.get(mode, {}).get(_language, mode)


def mode_hint(mode: str) -> str:
    from .config import MODE_HINTS

    return MODE_HINTS.get(mode, {}).get(_language, "")


__all__ = ["t", "has", "language", "set_language", "on_language_change",
           "mode_label", "mode_hint"]
