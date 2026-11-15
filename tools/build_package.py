"""Build the TongSheng distribution folder from a source checkout.

The packaged build is a plain folder (``dist/TongSheng-<version>``) that the
Inno Setup script turns into a spanned installer:

    python tools/build_package.py --stage      # collect files (hardlinks)
    python tools/build_package.py --stage --iss  # + dist/TongSheng.iss
    python tools/build_package.py --archive     # optional 7z split volumes

Only the files listed in ``SOURCES`` are copied; everything else (training
artifacts, logs, caches, the v3 vocoder, the duplicate ASR download) stays out.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

PRIVATE_VOICE = Path(r"C:\Local Repositories\PrivateVoice")
RUNTIME = PRIVATE_VOICE / "dist" / "PrivateVoice_Ahee52" / "runtime"
ASR_CACHE = PRIVATE_VOICE / "dist" / "PrivateVoice_Ahee52" / "models_cache"
GSV = PRIVATE_VOICE / "GPT-SoVITS"
ALT = Path(r"C:\Local Repositories\ALT-VoiceType")
LLAMA = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"

SKIP_DIRS = {".git", "__pycache__", "logs", "TEMP", ".venv", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".log"}


@dataclass
class Group:
    name: str
    dest: str
    files: list[Path] = field(default_factory=list)
    dirs: list[tuple[Path, str]] = field(default_factory=list)
    skip: tuple[str, ...] = ()
    bytes: int = 0


def _walk_files(root: Path, skip: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not any(s in d for s in skip)]
        for name in filenames:
            if name.endswith(tuple(SKIP_SUFFIXES)):
                continue
            if any(s in name for s in skip):
                continue
            out.append(Path(dirpath) / name)
    return out


def _llama_dir() -> Path | None:
    if not LLAMA.is_dir():
        return None
    for entry in sorted(LLAMA.glob("ggml.llamacpp*")):
        if (entry / "llama-server.exe").exists() or list(entry.rglob("llama-server.exe")):
            return entry
    return None


def build_groups() -> list[Group]:
    groups: list[Group] = []

    # 1. application code + docs
    app = Group("TongSheng 代码与文档", "")
    for rel in ("tongsheng", "tools", "docs", "tests"):
        if (ROOT / rel).is_dir():
            app.dirs.append((ROOT / rel, rel))
    for rel in ("run.bat", "README.md", "README.en.md", "CHANGELOG.md",
                "config.example.yaml", "requirements.txt", "LICENSE", "pyproject.toml"):
        if (ROOT / rel).exists():
            app.files.append((ROOT / rel, rel))
    groups.append(app)

    # 2. Python runtime
    runtime = Group("Python 运行时", "",
                    skip=("models_cache",))
    if RUNTIME.is_dir():
        runtime.dirs.append((RUNTIME, "runtime"))
    groups.append(runtime)

    # 3. GPT-SoVITS code (no weights) + the pretrained set v4 actually loads
    gsv_code = Group("GPT-SoVITS 代码", "",
                     skip=("pretrained_models", "GPT_weights", "SoVITS_weights"))
    if GSV.is_dir():
        for rel in ("GPT_SoVITS", "tools", "configs"):
            if (GSV / rel).is_dir():
                gsv_code.dirs.append((GSV / rel, f"GPT-SoVITS/{rel}"))
        for rel in ("config.py", "api.py", "api_v2.py", "webui.py", "LICENSE", "README.md"):
            if (GSV / rel).exists():
                gsv_code.files.append((GSV / rel, f"GPT-SoVITS/{rel}"))
    groups.append(gsv_code)

    pretrained = Group("v4 预训练权重", "")
    base = GSV / "GPT_SoVITS" / "pretrained_models"
    for rel in ("chinese-hubert-base", "chinese-roberta-wwm-ext-large",
                "fast_langdetect", "gsv-v4-pretrained"):
        if (base / rel).exists():
            pretrained.dirs.append(
                (base / rel, f"GPT-SoVITS/GPT_SoVITS/pretrained_models/{rel}"))
    for rel in ("s1v3.ckpt",):
        if (base / rel).exists():
            pretrained.files.append(
                (base / rel, f"GPT-SoVITS/GPT_SoVITS/pretrained_models/{rel}"))
    groups.append(pretrained)

    # 4. ASR models
    asr = Group("语音识别模型", "")
    scope = ASR_CACHE / "modelscope" / "models"
    if scope.is_dir():
        for entry in sorted(scope.iterdir()):
            if entry.is_dir():
                asr.dirs.append(
                    (entry, f"models/asr/modelscope/models/{entry.name}"))
    whisper = ASR_CACHE / "whisper" / "faster-whisper-small"
    if whisper.is_dir():
        asr.dirs.append((whisper, "models/asr/whisper/faster-whisper-small"))
    groups.append(asr)

    # 5. LLM weights
    llm = Group("LLM 权重", "")
    for name in ("Qwen3-1.7B-Q8_0.gguf", "Index-Translate-2B.Q4_K_M.gguf"):
        path = ALT / "models" / name
        if path.exists():
            llm.files.append((path, f"models/llm/{name}"))
    groups.append(llm)

    # 6. llama.cpp server
    llama = Group("llama-server", "")
    source = _llama_dir()
    if source is not None:
        llama.dirs.append((source, "llama"))
    groups.append(llama)

    # 6b. NLTK data required by the English front-end (g2p_en)
    nltk_src = Path(os.environ.get("APPDATA", "")) / "nltk_data"
    nltk = Group("NLTK 数据（英文音素）", "")
    if nltk_src.is_dir():
        nltk.dirs.append((nltk_src, "nltk_data"))
    groups.append(nltk)

    # 7. the shipped voice
    voice = Group("Default_Voice 音色", "")
    src = ROOT / "voice-repository" / "Default_Voice"
    if src.is_dir():
        voice.dirs.append((src, "voice-repository/Default_Voice"))
    groups.append(voice)

    # sizes
    for group in groups:
        total = 0
        for path, _rel in group.files:
            total += path.stat().st_size
        for root, _ in group.dirs:
            for path in _walk_files(root, group.skip):
                total += path.stat().st_size
        group.bytes = total
    return groups


def _force_remove(path: Path) -> None:
    """Remove a tree even when files are read-only (winget DLLs are)."""

    def retry(func, target, _exc):  # noqa: ANN001
        try:
            os.chmod(target, 0o666)
        except OSError:
            pass
        try:
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=retry)


def stage(groups: list[Group], dest: Path) -> None:
    if dest.exists():
        _force_remove(dest)
    dest.mkdir(parents=True, exist_ok=True)

    linked = copied = 0

    def link(src: Path, target: Path) -> None:
        nonlocal linked, copied
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return
        try:
            os.link(src, target)
            linked += 1
        except OSError:
            shutil.copy2(src, target)
            copied += 1

    for group in groups:
        base = dest / group.dest if group.dest else dest
        for src, rel in group.files:
            link(src, base / rel if rel else base / src.name)
        for root, rel in group.dirs:
            for path in _walk_files(root, group.skip):
                # rel already carries the in-package prefix for this group
                link(path, base / rel / path.relative_to(root))
    print(f"staged: {linked} hardlinked, {copied} copied -> {dest}")


def size_report(groups: list[Group]) -> str:
    total = sum(g.bytes for g in groups)
    lines = ["| 组成 | MB |", "|---|---:|"]
    for group in groups:
        lines.append(f"| {group.name} | {group.bytes / 1048576:.0f} |")
    lines.append(f"| **合计** | **{total / 1048576:.0f}** （{total / 1073741824:.2f} GB） |")
    return "\n".join(lines)


def write_iss(dest: Path, version: str, total_bytes: int) -> Path:
    """The installer script is versioned in the repo; just check it is ready."""
    iss = ROOT / "installer" / "TongSheng.iss"
    if not iss.exists():
        raise SystemExit(f"missing installer script: {iss}")
    # keep the wizard artwork and the app icon up to date
    assets = DIST / "installer_assets"
    if (assets / "app.ico").exists():
        target = dest / "app.ico"
        if not target.exists():
            target.write_bytes((assets / "app.ico").read_bytes())
    print(f"Inno Setup script: {iss}")
    print("   compile with:")
    print(f'   "C:\\Users\\%USERNAME%\\AppData\\Local\\Programs\\Inno Setup 6\\ISCC.exe" "{iss}"')
    return iss


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the TongSheng package")
    parser.add_argument("--stage", action="store_true", help="collect files into dist/")
    parser.add_argument("--iss", action="store_true", help="write the Inno Setup script")
    parser.add_argument("--archive", action="store_true", help="7z split volumes")
    args = parser.parse_args()

    version = "0.0.0"
    init = ROOT / "tongsheng" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"')
            break

    groups = build_groups()
    report = size_report(groups)
    print(report)
    total = sum(g.bytes for g in groups)

    dest = DIST / f"TongSheng-{version}"
    if args.stage:
        stage(groups, dest)
        manifest = {
            "version": version,
            "total_bytes": total,
            "groups": [{"name": g.name, "bytes": g.bytes} for g in groups],
        }
        DIST.mkdir(exist_ok=True)
        (DIST / "pack-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.iss:
        path = write_iss(dest, version, total)
        print(f"Inno Setup script: {path}")

    if args.archive:
        seven = shutil.which("7z") or r"C:\Program Files\7-Zip\7z.exe"
        if not Path(seven).exists():
            print("7-Zip not found; run this once it is installed:\n"
                  f'  7z a -t7z -mx=5 -v4096m "{DIST / ("TongSheng-" + version + ".7z")}" '
                  f'"{dest}\\*"')
        else:
            out = DIST / f"TongSheng-{version}.7z"
            subprocess.run([seven, "a", "-t7z", "-mx=5", "-v4096m", str(out),
                            f"{dest}\\*"], check=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
