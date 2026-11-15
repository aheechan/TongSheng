# TongSheng 1.1.2 — release notes

**Windows x64 · English installer · all models bundled**

> Fixes the launch failure in 1.1.1: the packaged build could not find its own model
> folders and `run.bat` looked for a development runtime that does not exist on a
> clean machine.

## Download (all 8 files are required)

| File | Size |
|---|---|
| `TongSheng-1.1.2-Setup.exe` | ~6 MB |
| `TongSheng-1.1.2-Setup-1.bin` … `-7.bin` | 1.77 GB each (last 52 MB) |

All 8 files total **10.67 GB**. Put them in the **same folder**, run the `.exe`, keep every `.bin` next to it.
A missing slice aborts the install. Verify with `SHA256SUMS.txt`.

## Requirements

- Windows 10 21H2+ / Windows 11 x64
- NVIDIA GPU, 6 GB VRAM minimum (16–24 GB recommended; RTX 50 series supported via CUDA 12.8)
- ~15 GB free disk, 16 GB RAM

## What is new in 1.1.2

- Packaged install now discovers its own models (`GPT-SoVITS`, `models\asr`, `models\llm`)
- Bundled `llama-server.exe` is preferred over anything on `PATH`
- FunASR cache uses the standard ModelScope layout
- `run.bat` prefers the bundled runtime and reports the exit code + log path on failure
- Startup failures show a dialog (the shortcut runs `pythonw.exe`, so there is no console)
- The installer now ships `tools\` — without it the shortcut could not start anything

## Install / uninstall

```bat
:: interactive
TongSheng-1.1.2-Setup.exe

:: silent
TongSheng-1.1.2-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

Installs to `%ProgramFiles%\TongSheng`, creates Start-menu entries (app, documentation,
uninstall) and an optional desktop shortcut. After installation the app lives in the
system tray: press **right Alt**, speak one sentence, press it again.

Diagnostics: `run.bat doctor` prints the resolved model paths, GPU and voice list;
logs are in `<install>\logs\app.log`, crashes in `<install>\logs\crash.log`.

## Upgrade from 1.1.1

Uninstall the old build first (it cannot start anyway), then install 1.1.2.
`config.yaml` from 1.1.1 is compatible; delete it to start from defaults.
