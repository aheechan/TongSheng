"""Turn one raw recording into the dataset GPT-SoVITS training expects.

Output layout (compatible with project A):

    <dataset>/clips/0001.wav …
    <dataset>/dataset.list      clips/0001.wav|speaker|ZH|文本
    <dataset>/metadata.json     duration / text / snr per clip
    <dataset>/reference.wav     a 5–10 s, clean clip used as prompt
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from ..audio import wav as wavmod
from ..logs import get_logger

log = get_logger("tts.dataset")

LANG_TAG = {"zh": "ZH", "en": "EN"}


@dataclass
class Clip:
    name: str
    samples: np.ndarray
    sr: int
    text: str = ""
    snr: float = 30.0

    @property
    def seconds(self) -> float:
        return len(self.samples) / float(self.sr or 1)


def split_on_silence(samples: np.ndarray, sr: int, min_silence: float = 0.32,
                     min_clip: float = 2.0, max_clip: float = 9.0,
                     floor_db: float = -42.0) -> list[np.ndarray]:
    """Energy based VAD splitter — good enough for a quiet home recording."""
    data = wavmod.to_mono(samples)
    if data.size == 0:
        return []
    frame = max(1, int(sr * 0.02))
    n = data.size // frame
    if n < 2:
        return [data]
    frames = data[:n * frame].reshape(n, frame)
    rms = 20.0 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-12)
    # adaptive floor: quietest 10% of frames + 8 dB
    adaptive = float(np.percentile(rms, 10)) + 8.0
    threshold = min(floor_db, adaptive)
    voiced = rms > threshold

    silence_frames = max(1, int(min_silence / 0.02))
    cuts: list[tuple[int, int]] = []
    start = None
    silence_run = 0
    for index, is_voiced in enumerate(voiced):
        if is_voiced:
            if start is None:
                start = index
            silence_run = 0
        else:
            if start is not None:
                silence_run += 1
                if silence_run >= silence_frames:
                    end = index - silence_run + 1
                    cuts.append((start, end))
                    start = None
                    silence_run = 0
    if start is not None:
        cuts.append((start, len(voiced)))

    pieces: list[np.ndarray] = []
    for begin, end in cuts:
        chunk = data[begin * frame:end * frame]
        if chunk.size < int(0.35 * sr):
            continue
        pieces.extend(_split_long_clip(chunk, sr, max_clip))
    merged = _merge_short(pieces, sr, min_clip)
    return merged


def _split_long_clip(chunk: np.ndarray, sr: int, max_clip: float) -> list[np.ndarray]:
    limit = int(max_clip * sr)
    if chunk.size <= limit:
        return [chunk]
    out: list[np.ndarray] = []
    position = 0
    while position < chunk.size:
        piece = chunk[position:position + limit]
        if piece.size >= int(1.0 * sr):
            out.append(piece)
        position += limit
    return out


def _merge_short(pieces: list[np.ndarray], sr: int, min_clip: float) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    buffer: list[np.ndarray] = []
    size = 0
    need = int(min_clip * sr)
    for piece in pieces:
        buffer.append(piece)
        size += piece.size
        if size >= need:
            out.append(np.concatenate(buffer))
            buffer, size = [], 0
    if buffer:
        tail = np.concatenate(buffer)
        if out and tail.size < need:
            out[-1] = np.concatenate([out[-1], tail])
        elif tail.size >= int(0.8 * sr):
            out.append(tail)
    return out


def build_dataset(source: str | Path, out_dir: str | Path,
                  asr_factory: Callable[[], object] | None = None,
                  language: str = "zh",
                  on_event: Callable[[str], None] | None = None) -> dict[str, object]:
    """Create clips + labels + dataset.list under ``out_dir``."""
    emit = on_event or (lambda _m: None)
    source_path = Path(source)
    audio, sr = wavmod.read_wav(source_path)
    audio = wavmod.peak_normalize(audio, 0.9)
    total = wavmod.duration(audio, sr)
    emit(f"loaded {total:.1f}s @ {sr} Hz")

    pieces = split_on_silence(audio, sr)
    if not pieces:
        raise ValueError("录音里没有可用的语音片段")
    emit(f"segmented into {len(pieces)} clips")

    clips_dir = Path(out_dir) / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    for stale in clips_dir.glob("*.wav"):
        stale.unlink()

    engine = asr_factory() if asr_factory else None
    clips: list[Clip] = []
    rows: list[str] = []
    for index, piece in enumerate(pieces, start=1):
        name = f"{index:04d}.wav"
        target = clips_dir / name
        wavmod.write_wav(target, piece, sr, subtype="PCM_16")
        text = ""
        if engine is not None:
            log.info("labelling clip %s (%.1fs audio) with %s",
                     name, piece.size / float(sr or 1), getattr(engine, "name", "asr"))
            started = time.perf_counter()
            try:
                result = engine.transcribe(wavmod.resample(piece, sr, 16000), 16000)
                text = (getattr(result, "text", "") or "").strip()
                log.info("clip %s: %.1fs audio -> %d chars in %.1fs",
                         name, piece.size / float(sr or 1), len(text),
                         time.perf_counter() - started)
            except Exception as exc:  # noqa: BLE001
                log.warning("labeling clip %s failed after %.1fs: %s", name,
                            time.perf_counter() - started, exc)
            log.info("labelled clip %s -> %d chars", name, len(text))
        if not text:
            target.unlink(missing_ok=True)
            continue
        clip = Clip(name=name, samples=piece, sr=sr, text=text,
                    snr=wavmod.rms_db(piece))
        clips.append(clip)
        rows.append(f"clips/{name}|speaker|{LANG_TAG.get(language, 'ZH')}|{text}")
        emit(f"labeled {index}/{len(pieces)}")

    if not clips:
        raise ValueError("所有片段都没有识别出文本，请换一段更清晰的录音")

    (Path(out_dir) / "dataset.list").write_text("\n".join(rows) + "\n", encoding="utf-8")
    metadata = {
        "source": str(source_path),
        "language": language,
        "clips": [
            {"file": f"clips/{c.name}", "text": c.text,
             "duration": round(c.seconds, 3), "snr": round(c.snr, 1),
             "flags": [], "status": "good"}
            for c in clips
        ],
    }
    (Path(out_dir) / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    reference = max(clips, key=lambda c: min(abs(c.seconds - 7.0), 3.0) * -1 + c.snr / 100.0)
    wavmod.write_wav(Path(out_dir) / "reference.wav", reference.samples,
                     reference.sr, subtype="PCM_16")
    (Path(out_dir) / "reference.txt").write_text(reference.text + "\n", encoding="utf-8")

    emit(f"dataset ready: {len(clips)} clips, {sum(c.seconds for c in clips):.1f}s speech")
    return {"clips": len(clips), "seconds": sum(c.seconds for c in clips),
            "reference": str(Path(out_dir) / "reference.wav"),
            "reference_text": reference.text}


__all__ = ["build_dataset", "split_on_silence", "Clip"]
