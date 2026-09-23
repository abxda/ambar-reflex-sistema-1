"""GPU watchdog: this RTX 3060 also drives the desktop; sustained load froze it once (NVRM Xid 56).
check() raises GpuUnsafe on a new Xid, temperature > 80 C, or < 2 GiB free VRAM."""

from __future__ import annotations

import subprocess
import time

MAX_TEMP_C = 80
MIN_FREE_MIB = 2048


class GpuUnsafe(RuntimeError):
    pass


def xid_count() -> int:
    try:
        out = subprocess.run(["journalctl", "-k", "-b", "--no-pager", "-q"], capture_output=True, text=True, timeout=20).stdout
        return out.count("NVRM: Xid")
    except Exception:  # noqa: BLE001
        return -1


def gpu_stats() -> dict:
    out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,memory.free,utilization.gpu",
                          "--format=csv,noheader,nounits", "-i", "0"], capture_output=True, text=True, timeout=10).stdout
    t, free, util = (int(x) for x in out.strip().split(","))
    return {"temp_c": t, "free_mib": free, "util": util}


class Guard:
    def __init__(self):
        self.baseline = xid_count()

    def check(self, where: str = "") -> dict:
        s = gpu_stats()
        x = xid_count()
        if self.baseline >= 0 and x > self.baseline:
            raise GpuUnsafe(f"{where}: new NVRM Xid in the kernel log ({x - self.baseline}) -> aborting")
        if s["temp_c"] > MAX_TEMP_C:
            raise GpuUnsafe(f"{where}: GPU at {s['temp_c']} C > {MAX_TEMP_C} C -> aborting")
        if s["free_mib"] < MIN_FREE_MIB:
            raise GpuUnsafe(f"{where}: only {s['free_mib']} MiB VRAM free -> aborting")
        return s

    def poll(self, every_s: float = 10.0) -> bool:
        """Cheap in-run check (at most every `every_s`): True means stop now."""
        now = time.time()
        if now - getattr(self, "_last", 0.0) < every_s:
            return False
        self._last = now
        try:
            self.check("in-run")
        except GpuUnsafe as e:
            self.tripped = str(e)
            return True
        return False

    def cooldown(self, seconds: int = 60, target_c: int = 60) -> None:
        """Wait at least `seconds`, and until the GPU is at or below target_c (max 5 min)."""
        t0 = time.time()
        time.sleep(seconds)
        while gpu_stats()["temp_c"] > target_c and time.time() - t0 < 300:
            time.sleep(10)
