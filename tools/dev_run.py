"""Development launcher: ``python tools/dev_run.py [command]``.

Works with the shared PrivateVoice runtime (isolated ``._pth``), which does not
add the project folder to ``sys.path`` automatically.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tongsheng.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
