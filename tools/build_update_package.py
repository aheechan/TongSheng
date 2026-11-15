"""Collect the delta between two releases: code, tools and docs only.

    python tools/build_update_package.py            # stage the update tree
    ISCC.exe installer\\TongSheng-update.iss       # compile the small installer

The result is a few MB, installs over an existing TongSheng folder and leaves
models, voices, recordings and config alone.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

INCLUDE_DIRS = ("tongsheng", "tools", "docs")
INCLUDE_FILES = ("run.bat", "README.md", "README.en.md", "CHANGELOG.md",
                 "config.example.yaml", "LICENSE", "pyproject.toml")
SKIP = {".git", "__pycache__", "logs", "results", "training", "dist"}


def version() -> str:
    for line in (ROOT / "tongsheng" / "__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=")[1].strip().strip('"')
    return "0.0.0"


def walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                continue
            out.append(Path(dirpath) / name)
    return out


def main() -> int:
    ver = version()
    target = DIST / f"TongSheng-{ver}-update"
    if target.exists():
        for dirpath, dirnames, filenames in os.walk(target):
            for name in filenames:
                try:
                    os.chmod(Path(dirpath) / name, 0o666)
                except OSError:
                    pass
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)

    total = 0
    for rel in INCLUDE_DIRS:
        src = ROOT / rel
        if not src.is_dir():
            continue
        for path in walk(src):
            dest = target / path.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            total += dest.stat().st_size

    for rel in INCLUDE_FILES:
        src = ROOT / rel
        if src.is_file():
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            total += dest.stat().st_size

    print(f"update tree: {target}")
    print(f"files     : {sum(1 for _ in target.rglob('*') if _.is_file())}")
    print(f"size      : {total / 1048576:.2f} MB (uncompressed)")
    print("compile   : ISCC.exe installer\\TongSheng-update.iss")
    return 0


if __name__ == "__main__":
    sys.exit(main())
