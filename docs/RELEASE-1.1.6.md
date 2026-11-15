# TongSheng 1.1.6 — update notes

Install on top of 1.1.5 (the update finds the existing install directory by itself).

## What changes

- **Training labels clips with faster-whisper**, not with the live Paraformer engine.
  Labelling dozens of short clips is a batch job; whisper is bundled, GPU-based and does not
  touch FunASR's model resolution. Live recognition still uses Paraformer.
- **45 s timeout per clip** - a stuck clip is skipped and logged instead of freezing training
- **Per-clip log lines** (`labelling clip 0003 …`), so a stall is always visible
- **Self-test now lists the voice library** and flags a missing `Default_Voice`
- Update still restores `Default_Voice` only when absent

## Apply

1. Quit TongSheng
2. Run `TongSheng-1.1.6-Update.exe`
3. Self-test: ten lines, all PASS
4. Train again; the log should show `labelling clip …` progressing and then
   `训练完成 / voice ready`
