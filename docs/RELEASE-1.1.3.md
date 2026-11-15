# TongSheng 1.1.3 — release notes

**Windows x64 · English installer · self-test included**

> 1.1.2 could start but could not speak English: the packaged `nltk_data` was hard-linked and
> NLTK's path security check refused it. 1.1.3 fixes that, restores voice training in the
> installed build, and adds a post-install self test.

## Download (all files required)

| File | Size |
|---|---|
| `TongSheng-1.1.3-Setup.exe` | ~6 MB |
| `TongSheng-1.1.3-Setup-1.bin` … `-6.bin` | 1.77 GB each |
| `SHA256SUMS.txt` | checksums |

Put every file in one folder and run the `.exe`. A missing slice aborts the install.

## What is new

- **English synthesis works**: `nltk_data` is copied, not linked, so NLTK no longer raises
  `Security Violation [pathsec.open]`
- **Voice training works in the installed build**: project A's `app/` training backend
  (dataset prep, LoRA, self-test) now ships with the package
- **Writable data folder**: when the install directory is read-only (Program Files), config,
  logs, recordings and trained voices go to `%LOCALAPPDATA%\TongSheng`
- **Self-test** (`tools/selftest.py`, also in the Start menu): Python/torch, GPU + VRAM,
  model folders and v4 weights, llama-server, audio endpoints, English NLTK data, ASR load,
  English synthesis, training backend. Report: `logs\selftest.txt`.
  The setup offers "Run the self-test now" on the final page.
- **No 950 MB duplicate**: `MODELSCOPE_CACHE` now points at `models\asr\modelscope`, so
  ModelScope reuses the bundled paraformer instead of copying it on first load
- FunASR keeps the full CUDA failure traceback for diagnosis on RTX 50 series

## Requirements

- Windows 10 21H2+ / 11 x64, NVIDIA GPU with 6 GB VRAM (16–24 GB recommended)
- ~15 GB disk, 16 GB RAM; CUDA 12.8 driver (570.x or newer)

## Install

```bat
TongSheng-1.1.3-Setup.exe
:: silent
TongSheng-1.1.3-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

If something is off, run the self-test first and attach `logs\selftest.txt` plus
`logs\app.log` when reporting.
