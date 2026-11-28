"""Voice profiles: the cloned voices TongSheng can speak with.

A profile is a folder::

    voices/<id>/
        profile.json
        reference.wav
        reference.txt
        checkpoints/...      # optional LoRA weights

``profile.json`` is compatible with the PrivateVoice character layout, so an
existing trained voice can be imported without retraining.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..logs import get_logger

log = get_logger("tts.voices")


@dataclass
class VoiceProfile:
    id: str
    name: str
    mode: str = "finetune"          # finetune | zero-shot
    gpt_ckpt: str = ""              # GPT (s1) weights, shared by both tiers
    sovits_live: str = ""           # low tier SoVITS (v3 32k-family / v4 fallback)
    sovits_rec: str = ""            # high tier SoVITS (v4 48k)
    reference: str = "reference.wav"
    reference_text: str = ""
    reference_lang: str = "zh"
    created_at: str = ""
    notes: str = ""
    dir: str = field(default="", compare=False)

    # -- helpers --------------------------------------------------------
    @property
    def root(self) -> Path:
        return Path(self.dir) if self.dir else Path(".")

    def resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    @property
    def reference_path(self) -> Path:
        return self.resolve(self.reference)

    def checkpoint(self, mode: str) -> str:
        preferred = self.sovits_rec if mode == "rec" else self.sovits_live
        if preferred:
            return str(self.resolve(preferred))
        # fall back to whichever tier exists
        other = self.sovits_live if mode == "rec" else self.sovits_rec
        return str(self.resolve(other)) if other else ""

    @property
    def gpt_path(self) -> str:
        return str(self.resolve(self.gpt_ckpt)) if self.gpt_ckpt else ""

    @property
    def trained(self) -> bool:
        return self.mode == "finetune" and bool(self.gpt_ckpt)

    def missing_files(self) -> list[str]:
        missing: list[str] = []
        if self.trained and not Path(self.gpt_path).exists():
            missing.append(self.gpt_ckpt)
        if not self.reference_path.exists():
            missing.append(self.reference)
        if self.trained and not any(Path(self.checkpoint(m)).exists() for m in ("live", "rec")):
            missing.append("sovits checkpoint")
        return missing

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("dir", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], directory: str = "") -> "VoiceProfile":
        allowed = {f for f in cls.__dataclass_fields__ if f != "dir"}
        kwargs = {k: v for k, v in data.items() if k in allowed}
        kwargs.setdefault("id", slugify(kwargs.get("name", "voice")))
        profile = cls(**kwargs)
        profile.dir = directory
        # accept the PrivateVoice layout (voice.* nested dict)
        voice = data.get("voice") if isinstance(data.get("voice"), dict) else None
        if voice:
            profile.gpt_ckpt = profile.gpt_ckpt or str(voice.get("gpt_ckpt") or "")
            if not profile.sovits_rec:
                sovits = str(voice.get("sovits_ckpt") or "")
                if sovits:
                    if "_l32" in sovits or "v3" in sovits.lower():
                        profile.sovits_live = profile.sovits_live or sovits
                    else:
                        profile.sovits_rec = profile.sovits_rec or sovits
            profile.reference = str(voice.get("reference") or profile.reference)
            profile.reference_text = str(voice.get("reference_text") or profile.reference_text)
            profile.mode = str(voice.get("mode") or profile.mode)
        return profile


class VoiceStore:
    PV_PREFIX = "pv:"

    def __init__(self, root: str | Path, external_root: str | Path | None = None) -> None:
        self.root = Path(root)
        self.external_root = Path(external_root) if external_root else None
        self._cache: dict[str, VoiceProfile] = {}

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[VoiceProfile]:
        self.ensure()
        profiles: dict[str, VoiceProfile] = {}
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            cfg = path / "profile.json"
            if not cfg.exists():
                continue
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("bad voice profile %s: %s", cfg, exc)
                continue
            profile = VoiceProfile.from_dict(data, str(path))
            profiles[profile.id] = profile
        for profile in self._external_voices():
            profiles.setdefault(profile.id, profile)
        self._cache = profiles
        return sorted(profiles.values(), key=lambda p: p.created_at or p.name)

    def get(self, voice_id: str) -> VoiceProfile | None:
        if voice_id in self._cache:
            return self._cache[voice_id]
        if str(voice_id).startswith(self.PV_PREFIX):
            for profile in self._external_voices():
                if profile.id == voice_id:
                    self._cache[voice_id] = profile
                    return profile
            return None
        self.list()
        return self._cache.get(voice_id)

    # -- PrivateVoice characters, used in place --------------------------
    def _external_voices(self) -> list[VoiceProfile]:
        """Read project A's ``characters/*`` folders without copying anything."""
        base = self.external_root
        if base is None or not base.is_dir():
            return []
        found: list[VoiceProfile] = []
        for folder in sorted(base.iterdir()):
            if not folder.is_dir():
                continue
            cfg = folder / "profile.json"
            if not cfg.exists():
                continue
            try:
                data = json.loads(cfg.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue
            profile = _profile_from_private_voice(folder, data, self.PV_PREFIX)
            if profile is not None:
                found.append(profile)
        return found

    def first(self) -> VoiceProfile | None:
        voices = self.list()
        return voices[0] if voices else None

    def save(self, profile: VoiceProfile) -> Path:
        if str(profile.id).startswith(self.PV_PREFIX):
            raise ValueError("PrivateVoice voices are read in place and cannot be saved here")
        self.ensure()
        folder = Path(profile.dir) if profile.dir else self.root / profile.id
        folder.mkdir(parents=True, exist_ok=True)
        profile.dir = str(folder)
        payload = profile.to_dict()
        payload["id"] = profile.id
        (folder / "profile.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._cache[profile.id] = profile
        return folder

    # -- import ---------------------------------------------------------
    def import_private_voice(self, source: str | Path, voice_id: str | None = None,
                             display_name: str = "") -> VoiceProfile:
        """Copy a PrivateVoice character folder into the TongSheng voice store."""
        src = Path(source)
        if not src.is_dir():
            raise FileNotFoundError(f"voice folder not found: {src}")
        cfg_path = src / "profile.json"
        data: dict[str, Any] = {}
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        name = display_name or str(data.get("name") or src.name)
        vid = voice_id or f"{slugify(name)}-{_short_hash(str(src))}"
        dest = self.root / vid
        dest.mkdir(parents=True, exist_ok=True)

        # reference audio + transcript
        ref_name = "reference.wav"
        for candidate in (src / "reference.wav", src / "dataset" / "reference.wav"):
            if candidate.exists():
                shutil.copy2(candidate, dest / ref_name)
                break
        text = ""
        for ref_txt in (src / "reference.txt", src / "reference(1).txt"):
            if ref_txt.exists():
                text = ref_txt.read_text(encoding="utf-8", errors="replace").strip()
                (dest / "reference.txt").write_text(text + "\n", encoding="utf-8")
                break

        # checkpoints: skip "(1)" style duplicates that cloud sync leaves behind
        ckpt_dir = src / "checkpoints"
        gpt_rel = sovits_live = sovits_rec = ""
        if ckpt_dir.is_dir():
            target = dest / "checkpoints"
            target.mkdir(parents=True, exist_ok=True)
            files = [item for item in ckpt_dir.iterdir()
                     if item.is_file() and item.suffix in (".pth", ".ckpt")]
            primary = [item for item in files if not _is_duplicate(item.name)] or files
            for item in primary:
                shutil.copy2(item, target / item.name)
            for item in sorted(target.iterdir()):
                rel = f"checkpoints/{item.name}"
                if item.suffix == ".ckpt":
                    gpt_rel = gpt_rel or rel
                elif "_l48" in item.name:
                    sovits_rec = sovits_rec or rel
                else:
                    sovits_live = sovits_live or rel
        # Keep the checkpoint on both tiers; the runtime compares the header
        # version with the tier and falls back to the base model when needed.
        sovits_live = sovits_live or sovits_rec
        sovits_rec = sovits_rec or sovits_live

        # profile.json in A may point at absolute C:\VoiceLab paths: ignore those
        voice = data.get("voice") or {}
        ref_text = text or str(voice.get("reference_text") or "")
        profile = VoiceProfile(
            id=vid,
            name=name,
            mode="finetune" if gpt_rel else "zero-shot",
            gpt_ckpt=gpt_rel,
            sovits_live=sovits_live,
            sovits_rec=sovits_rec or sovits_live,
            reference=ref_name,
            reference_text=ref_text,
            reference_lang="zh",
            created_at=datetime.now().isoformat(timespec="seconds"),
            notes=f"imported from {src}",
        )
        self.save(profile)
        log.info("imported voice %s -> %s", name, dest)
        return profile


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "voice").strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text)
    return text.strip("-") or "voice"


def _is_duplicate(name: str) -> bool:
    """``vlab_x-e10(1).ckpt`` style copies left by sync tools."""
    import re

    return bool(re.search(r"\(\d+\)", name))


def _short_hash(value: str) -> str:
    import hashlib

    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:6]


__all__ = ["VoiceProfile", "VoiceStore", "slugify"]


def _resolve_private_path(folder: Path, value: str) -> str:
    """A stores absolute paths that may not exist after moving the folder."""
    raw = (value or "").strip()
    if not raw:
        return ""
    candidate = Path(raw)
    if candidate.is_absolute() and candidate.exists():
        return str(candidate)
    local = folder / "checkpoints" / candidate.name
    if local.exists():
        return str(local)
    return ""


def _profile_from_private_voice(folder: Path, data: dict[str, Any],
                                prefix: str) -> VoiceProfile | None:
    voice = data.get("voice") if isinstance(data.get("voice"), dict) else data
    gpt = _resolve_private_path(folder, str(voice.get("gpt_ckpt") or ""))
    sovits = _resolve_private_path(
        folder,
        str(voice.get("sovits_ckpt") or voice.get("sovits_rec")
            or voice.get("sovits_live") or ""))
    reference = folder / "reference.wav"
    if not reference.exists():
        reference = folder / "dataset" / "reference.wav"
    if not reference.exists():
        return None

    text = str(voice.get("reference_text") or "").strip()
    if not text:
        for name in ("reference.txt", "dataset/reference.txt"):
            candidate = folder / name
            if candidate.exists():
                text = candidate.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    break

    trained = bool(gpt and sovits)
    return VoiceProfile(
        id=f"{prefix}{data.get('id') or folder.name}",
        name=str(data.get("name") or folder.name),
        mode="finetune" if trained else "zero-shot",
        gpt_ckpt=gpt,
        sovits_live=sovits,
        sovits_rec=sovits,
        reference=str(reference),
        reference_text=text,
        reference_lang="",
        created_at=str(data.get("created_at") or ""),
        notes="PrivateVoice (live)",
        dir=str(folder),
    )


def make_voice_store(models: Any) -> VoiceStore:
    """Voice store that also exposes project A's characters in place."""
    root = models.characters or Path("voices")
    pv_root = getattr(models, "private_voice", None)
    external = (Path(pv_root) / "characters") if pv_root is not None else None
    return VoiceStore(root, external_root=external)
