"""GPU information.

Policy: we do NOT throttle or refuse work based on free VRAM. The product runs
on everything from an 8 GB card upward; if a task does not fit the driver will
complain (or the display glitches) and the user decides what to do. This module
only reports numbers for the log / self-test.
"""

from __future__ import annotations

from dataclasses import dataclass

from .logs import get_logger

log = get_logger("vram")


@dataclass
class GpuInfo:
    name: str = "unknown"
    total_gb: float = 0.0
    free_gb: float = 0.0

    def describe(self) -> str:
        return (f"{self.name} · {self.total_gb:.1f} GB"
                f"（当前空闲 {self.free_gb:.1f} GB）")


def detect() -> GpuInfo:
    info = GpuInfo()
    try:
        import torch

        if not torch.cuda.is_available():
            return info
        info.name = torch.cuda.get_device_name(0)
        free, total = torch.cuda.mem_get_info(0)
        info.free_gb = free / 1024 ** 3
        info.total_gb = total / 1024 ** 3
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot read GPU memory: %s", exc)
        return info
    log.info("GPU: %s", info.describe())
    return info


__all__ = ["GpuInfo", "detect"]
