# TongSheng · 同声

**Your voice, any language.**

Real-time speech translation in your own cloned voice — fully local on Windows.

Say something with a hotkey held down. TongSheng recognises the speech, fixes
recognition errors, translates it, and speaks the translation **in your own
cloned voice**.

- Chinese ⇄ English, switched from the tray (UI language *and* ASR model together)
- Two output tiers: **LIVE 24 kHz** (streaming, latency first) and **REC 48 kHz**
  (whole-sentence, quality first)
- Nothing leaves the machine: FunASR / faster-whisper → local LLM correction →
  Index-Translate → GPT-SoVITS

> Voice cloning requires explicit consent from the voice owner. Clone only your
> own voice, or a voice you have written permission to use.

## Pipeline

```
mic → ASR (FunASR zh / faster-whisper en) → correct (Qwen3-1.7B)
    → translate (Index-Translate-9B) → TTS (GPT-SoVITS v3/v4) → speaker
```

## Two quality tiers

| | LIVE (low) | REC (high) |
|---|---|---|
| Sample rate | **24 kHz** | **48 kHz** |
| Model | GPT-SoVITS **v3** (zero-shot if no v3 LoRA) | GPT-SoVITS **v4 + trained LoRA** (48 kHz vocoder) |
| Synthesis | streamed fragments, first audio fast | whole sentence, then play |
| Extra | — | each take saved to `results/rec/*.wav` |

Switch at any time from **Output quality** in the tray.

## Quick start

```bat
run.bat            :: tray app
run.bat doctor     :: environment check (paths / GPU / voices)
run.bat voices import --from "..\PrivateVoice\characters\<voice>"
run.bat train --audio D:\my-recording.wav --name "my voice"
```

During the test phase TongSheng reuses the weights of two sibling projects
(`../PrivateVoice`, `../ALT-VoiceType`) and does not copy them. Point
`config.yaml` at other locations if needed.

Press and hold **Ctrl+Alt** to talk, or use the tray's *Start talking* item.

## Layout

```
tongsheng/   audio · asr · correct · translate · llm · tts · service · tray
voices/      cloned voices (not committed)
results/     history and recordings
tests/       unit tests (no GPU required)
```

## Credits

GPT-SoVITS (MIT), FunASR (MIT), faster-whisper (MIT), llama.cpp (MIT),
Index-Translate, PySide6 (LGPLv3). Integrated from **PrivateVoice** (MIT) and
**ALT-VoiceType** (Apache-2.0). See [THIRD_PARTY.md](THIRD_PARTY.md).

Code: MIT. Model weights keep their own licences.
