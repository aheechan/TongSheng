# TongSheng 1.1.4 — update notes

**Small update (2.2 MB). Install it on top of an existing TongSheng 1.1.3.**

## Why

On RTX 50 series (Blackwell) FunASR refused to start on CUDA:

```
FunASR load failed on cuda / cuda:0 / cuda (lazy): 'NoneType' object is not callable
```

1.1.3 removed the CPU fallback, so Chinese ASR never loaded: warm-up hung, the UI stayed on
"recognising", and training stopped at the segmentation stage (it needs ASR too).

## What changed

- **GPU engine fallback**: FunASR (Paraformer) → faster-whisper on the *same* GPU, which is
  already bundled. CPU is still never used (`asr.allow_cpu_fallback` stays false).
  Disable the chain with `asr.gpu_fallback: ""` if you want FunASR only.
- **Full traceback** of every FunASR load failure is written to `logs/app.log`.
- **`tools/asr_probe.py`** prints the GPU, the three CUDA load attempts with tracebacks and
  whether the whisper fallback works.

## Apply

1. Close TongSheng (tray → 退出)
2. Run `TongSheng-1.1.4-Update.exe` (English wizard, installs over the existing folder)
3. Start menu → **Self-test** should report 9 × PASS
4. If ASR still fails, run `runtime\python.exe tools\asr_probe.py` and send the output

Nothing else is touched: models, voices, recordings and `config.yaml` stay as they are.
