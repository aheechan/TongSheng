# TongSheng 1.1.11-beta — Text-to-Audio Mode

**Beta branch:** `TongSheng-1.1.11-beta-TextRec_mode` (commit `b1a28f0`)
**Package:** `TongSheng-1.1.11-beta-TextRec_mode-update.zip` — 0.49 MB, code-only overlay
**Requires:** an installed **TongSheng 1.1.11** (full package)
**SHA256:** `1096cd909501110000ff7241b241e53e4a54fc033a50f889b87bf982a4b0ae69`

---

## What this beta adds

A second working mode: instead of speaking, you type text — the app translates it, speaks the translation in your cloned voice and saves it as a WAV file.

### Mode switch

- The header (right of **Voice model training**) shows the active mode as a highlighted status chip — inverse colours, so it reads as state rather than as a control.
- The button underneath reads **Switch mode**; clicking it toggles between *Voice input* and *Text to audio*.
- Voice input mode keeps the original blue-tinted dark theme. Text-to-audio mode shifts the whole window to a subtle emerald dark tone, so the active mode is recognisable at a glance while staying dark.
- The mode is remembered in `config.yaml` and restored on the next start.

### In text-to-audio mode

- The *Save synthesised audio* row is replaced by a **three-line, scrollable text box** using the same styling as the transcript below it. `Ctrl+Enter` submits; `Enter` inserts a newline.
- **Input language is detected automatically** from the script: Kana → Japanese, Hangul → Korean, Han → Chinese, everything else → English. The bundled speech front-end supports Chinese, English, Japanese, Korean and Cantonese.
- The primary action button becomes the text-recording action. The result is written to
  `results\rec-text\YYYYmmdd-HHMMSS-48k.wav` (48 kHz PCM WAV) and played back in your cloned voice.
- The language toggle label changes from *Input language* to **UI language**: it now only switches the interface between Chinese and English and no longer reloads the recogniser.
- **The ASR engine is released on entry** (engine closed, CUDA cache emptied) and **reloaded and warmed automatically** when you switch back to voice input.
- The microphone level meter and the warm-up button are hidden, because no audio capture is involved.

## Fixed in this beta

- **An explicit output language is now honoured.** Previously, with output language set to Chinese and Chinese text typed, the text was force-translated to English and spoken in English. An explicit choice always wins now; only an empty setting falls back to the opposite language.
- **The upgrade guard is scoped correctly.** The overlay used to abort when *any* `pythonw.exe` process existed on the machine. It now only refuses when TongSheng itself is running from the target installation directory.

## How to install

1. Quit TongSheng from the tray.
2. Extract `TongSheng-1.1.11-beta-TextRec_mode-update.zip` into a subfolder of the installation directory, for example
   `D:\TongSheng\TongSheng-1.1.11-beta-TextRec_mode\`.
3. Run `apply_update.bat` inside that folder. It prints `Installed version: 1.1.11`.
4. Start TongSheng and run **Self-test** from the Start menu — all ten checks must pass.

The overlay replaces program code, tools and documentation only. Models, `config.yaml`, recordings and trained voices (`voice-repository`) are left untouched, and nothing is deleted.

## Known limitations

- Text mode performs no speech recognition; the ASR model is unloaded on purpose.
- Translation still goes through the bundled local llama.cpp servers, which the app starts automatically when needed.
- Language detection is script based, so mixed-language text may be attributed to its dominant script.
- This beta ships as a code overlay only — it cannot set up a new machine. Install 1.1.11 first.
