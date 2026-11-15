"""GPU memory budget.

Target hardware is deliberately broad: an 8 GB card must be able to run the
translator, so nothing is kept resident that is not needed right now.
"""

from __future__ import annotations

from dataclasses import dataclass

from .logs import get_logger

log = get_logger("vram")

PROFILES = {
    "8gb": {"llm_resident": False, "translator": "Index-Translate-2B",
            "training": False, "idle_stop_s": 90},
    "12gb": {"llm_resident": True, "translator": "Index-Translate-2B",
             "training": True, "idle_stop_s": 0},
    "24gb": {"llm_resident": True, "translator": "Index-Translate-9B",
             "training": True, "idle_stop_s": 0},
}


@dataclass
class GpuBudget:
    name: str = "unknown"
    total_gb: float = 0.0
    free_gb: float = 0.0
    profile: str = "12gb"

    @property
    def llm_resident(self) -> bool:
        return bool(PROFILES[self.profile]["llm_resident"])

    @property
    def training_allowed(self) -> bool:
        return bool(PROFILES[self.profile]["training"])

    @property
    def idle_stop_s(self) -> int:
        return int(PROFILES[self.profile]["idle_stop_s"])

    def describe(self) -> str:
        return (f"{self.name} · {self.total_gb:.1f} GB（空闲 {self.free_gb:.1f}）"
                f" · 档位 {self.profile}")


def detect() -> GpuBudget:
    budget = GpuBudget()
    try:
        import torch

        if not torch.cuda.is_available():
            budget.profile = "8gb"
            return budget
        budget.name = torch.cuda.get_device_name(0)
        free, total = torch.cuda.mem_get_info(0)
        budget.free_gb = free / 1024 ** 3
        budget.total_gb = total / 1024 ** 3
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot read GPU memory: %s", exc)
        return budget

    if budget.total_gb < 10.0:
        budget.profile = "8gb"
    elif budget.total_gb < 18.0:
        budget.profile = "12gb"
    else:
        budget.profile = "24gb"
    log.info("GPU profile: %s", budget.describe())
    return budget


__all__ = ["GpuBudget", "PROFILES", "detect"]
