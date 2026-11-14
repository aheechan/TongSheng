"""Clone training: one uploaded recording in, one usable voice out.

The heavy lifting (dataset prep, LoRA training, self-test) is delegated to
project A's ``app.core.train`` — the same code path that already produced the
voices in ``PrivateVoice/characters``. TongSheng keeps the resulting weights in
its own ``voices/`` folder so packaging stays self-contained.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..config import AppConfig
from ..logs import get_logger
from ..paths import ModelPaths
from .dataset import build_dataset
from .voices import VoiceProfile, VoiceStore, slugify

log = get_logger("tts.trainer")


@dataclass
class TrainProgress:
    stage: str
    message: str = ""
    epoch: int = 0
    total_epochs: int = 0


class TrainError(RuntimeError):
    pass


class CloneTrainer:
    def __init__(self, config: AppConfig, models: ModelPaths,
                 asr_factory: Callable[[], Any] | None = None,
                 on_event: Callable[[TrainProgress], None] | None = None) -> None:
        self.config = config
        self.models = models
        self.asr_factory = asr_factory
        self.on_event = on_event or (lambda _p: None)
        self._runner: Any = None

    # -- availability ---------------------------------------------------
    def source_root(self) -> Path | None:
        if self.models.gpt_sovits is None:
            return None
        return self.models.gpt_sovits.parent

    def available(self) -> tuple[bool, str]:
        root = self.source_root()
        if root is None:
            return False, "未找到 GPT-SoVITS"
        if not (root / "app" / "core" / "train.py").exists():
            return False, f"未找到项目A训练模块：{root / 'app' / 'core' / 'train.py'}"
        return True, ""

    # -- training -------------------------------------------------------
    def train(self, name: str, source: str | Path, epochs: int | None = None,
              profile: str = "conservative", language: str = "zh") -> VoiceProfile:
        ok, reason = self.available()
        if not ok:
            raise TrainError(reason)
        root = self.source_root()
        assert root is not None
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from app.config import Config  # project A
        from app.core import train as a_train
        from app.core.characters import CharacterStore

        source_path = Path(source)
        if not source_path.exists():
            raise TrainError(f"音频不存在：{source_path}")

        cfg = Config.load()
        cfg.set("paths.gpt_sovits", str(self.models.gpt_sovits))
        cfg.set("paths.characters", str(root / "characters"))
        cfg.set("paths.datasets", str(root / "datasets"))
        cfg.set("paths.logs", str(root / "logs"))
        cfg.set("training.s2_version", "v4")
        store = CharacterStore(cfg.path_of("characters"))

        display = name.strip() or "我的声音"
        if store.name_taken(display):
            display = f"{display}-{time.strftime('%H%M%S')}"
        character = store.create(display)
        dataset_dir = Path(cfg.path_of("datasets")) / character.id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dataset_dir / "source.wav")

        self.on_event(TrainProgress("dataset", "正在切分并识别录音…"))
        stats = build_dataset(
            source_path, dataset_dir,
            asr_factory=self.asr_factory, language=language,
            on_event=lambda msg: self.on_event(TrainProgress("dataset", msg)))
        log.info("dataset: %s", stats)
        self.on_event(TrainProgress(
            "dataset", f"{stats['clips']} 个片段 / {stats['seconds']:.1f}s 语音"))

        info = a_train.gpu_info()
        plan = cfg.plan(info.total_gb, profile)
        if epochs:
            try:
                plan.epochs = int(epochs)
            except Exception:
                pass

        def relay(event: Any) -> None:
            self.on_event(TrainProgress(
                stage=str(getattr(event, "stage", "")),
                message=str(getattr(event, "message", "")),
                epoch=int(getattr(event, "epoch", 0) or 0),
                total_epochs=int(getattr(event, "total_epochs", 0) or 0)))

        self.on_event(TrainProgress("train", f"开始训练（{plan.epochs} epochs）…"))
        runner = a_train.TrainingRunner(cfg, store, character.id, dataset_dir, plan,
                                        on_event=relay)
        self._runner = runner
        started = time.time()
        result = runner.run()
        self._runner = None
        minutes = (time.time() - started) / 60.0
        log.info("training finished in %.1f min: %s", minutes, result)

        return self._install_voice(display, character, result, dataset_dir)

    def cancel(self) -> None:
        runner = self._runner
        if runner is not None:
            try:
                runner.cancel()
            except Exception:
                pass

    # -- install --------------------------------------------------------
    def _install_voice(self, name: str, character: Any, result: dict[str, Any],
                       dataset_dir: Path) -> VoiceProfile:
        store = VoiceStore(self.models.characters or Path("voices"))
        voice_id = f"{slugify(name)}-{character.id.split('-')[-1]}"
        target = store.root / voice_id
        target.mkdir(parents=True, exist_ok=True)
        ckpt_dir = target / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        gpt_src = Path(str(result.get("gpt") or ""))
        sovits_src = Path(str(result.get("sovits") or ""))
        gpt_rel = sovits_rel = ""
        if gpt_src.exists():
            shutil.copy2(gpt_src, ckpt_dir / gpt_src.name)
            gpt_rel = f"checkpoints/{gpt_src.name}"
        if sovits_src.exists():
            shutil.copy2(sovits_src, ckpt_dir / sovits_src.name)
            sovits_rel = f"checkpoints/{sovits_src.name}"

        ref_src = Path(str(result.get("reference") or ""))
        if not ref_src.exists():
            ref_src = dataset_dir / "reference.wav"
        ref_text = ""
        if ref_src.exists():
            shutil.copy2(ref_src, target / "reference.wav")
            text_file = ref_src.with_suffix(".txt")
            if text_file.exists():
                ref_text = text_file.read_text(encoding="utf-8", errors="replace").strip()
        if not ref_text:
            meta = dataset_dir / "metadata.json"
            if meta.exists():
                try:
                    data = json.loads(meta.read_text(encoding="utf-8"))
                    for clip in data.get("clips", []):
                        if Path(str(clip.get("file"))).name == ref_src.name:
                            ref_text = str(clip.get("text") or "")
                except Exception:
                    pass
        if ref_text:
            (target / "reference.txt").write_text(ref_text + "\n", encoding="utf-8")

        from ..text import detect_language

        profile = VoiceProfile(
            id=voice_id,
            name=name,
            mode="finetune" if gpt_rel and sovits_rel else "zero-shot",
            gpt_ckpt=gpt_rel,
            sovits_live="",           # LIVE tier falls back to the v3 base model
            sovits_rec=sovits_rel,
            reference="reference.wav",
            reference_text=ref_text,
            reference_lang=detect_language(ref_text) if ref_text else "zh",
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            notes=f"trained from {dataset_dir}",
        )
        store.save(profile)
        self.on_event(TrainProgress("done", f"音色已就绪：{name}"))
        return profile


__all__ = ["CloneTrainer", "TrainProgress", "TrainError"]
