# TongSheng 1.1.5 — update notes

**Update package (~200 MB, contains the default voice), installs over the existing folder.**

## The real bug behind the RTX 50 failure

```
File "funasr/auto/auto_model.py", line 213, in build_model
    model = model_class(**model_conf, vocab_size=vocab_size)
TypeError: 'NoneType' object is not callable
```

`model_class` comes from `tables.model_classes.get(kwargs["model"])`. We used to pass the
*name* `paraformer-zh`; FunASR then resolves name → local directory and merges that folder's
`config.yaml`, which finally sets the real class key. When that resolution lands on a folder
without `config.yaml`, `kwargs["model"]` stays a plain name and the registry lookup returns
`None` - hence the TypeError. It is a **model-path problem, not a GPU problem**; it only looked
GPU-related because 1.1.3 stopped trying CPU.

## Fix

- FunASR now receives the **local model directory** (`.../snapshots/master`), so no name
  lookup and no hub access happens; a missing `config.yaml` raises a precise error instead.
- Update package finds the previous install directory in the registry (works for `D:\TongSheng`).
- Default voice is restored only if missing (`onlyifdoesntexist`).
- Self-test reports the real engine/device even with the GPU fallback wrapper.

## Apply

1. Quit TongSheng
2. Run `TongSheng-1.1.5-Update.exe`
3. Start menu -> Self-test: all nine lines must be PASS, including
   `ASR engine loads: funasr-paraformer loaded on cuda`
