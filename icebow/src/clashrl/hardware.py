"""What this PC actually has, and what that means for the simulator's settings.

Used by the launcher to propose settings instead of leaving `sim.envs` at its
one-size-fits-all default. The proposal is only a STARTING POINT -- the honest
number comes from `run.py sim-bench`, which measures matches/second on this
machine (see `bench.py`). Nothing here writes anything.
"""
from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict, Optional


def _total_ram_bytes() -> Optional[int]:
    if os.name == "nt":
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MemStatus()
        st.dwLength = ctypes.sizeof(_MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys)
        return None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def _avail_ram_bytes() -> Optional[int]:
    if os.name == "nt":
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MemStatus()
        st.dwLength = ctypes.sizeof(_MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullAvailPhys)
    return None


def rss_bytes() -> Optional[int]:
    """Resident memory of THIS process, so the benchmark can see what a pool of envs costs."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        c = _Counters()
        c.cb = ctypes.sizeof(_Counters)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
            return int(c.WorkingSetSize)
        return None
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except OSError:
        return None


def free_ram_bytes() -> Optional[int]:
    return _avail_ram_bytes()


def probe() -> Dict[str, Any]:
    """Read the machine. Never raises -- unknown fields come back as None."""
    info: Dict[str, Any] = {
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "cpu_logical": os.cpu_count(),
        "cpu_name": platform.processor() or None,
        "ram_total": _total_ram_bytes(),
        "ram_available": _avail_ram_bytes(),
        "gpu": None, "gpu_vram": None, "gpu_sm": None,
        "torch": None, "cuda": None, "cuda_available": False, "torch_threads": None,
    }
    try:
        import torch
        info["torch"] = torch.__version__
        info["torch_threads"] = torch.get_num_threads()
        info["cuda"] = getattr(torch.version, "cuda", None)
        if torch.cuda.is_available():
            info["cuda_available"] = True
            p = torch.cuda.get_device_properties(0)
            info["gpu"] = p.name
            info["gpu_vram"] = int(p.total_memory)
            info["gpu_sm"] = int(p.multi_processor_count)
    except Exception as exc:                              # noqa: BLE001 -- torch is optional here
        info["torch_error"] = str(exc)
    return info


def suggest(info: Dict[str, Any], cur_envs: int = 8) -> Dict[str, Any]:
    """A first guess at simulator settings for this machine, with the reasoning.

    Deliberately conservative and explicitly labelled a guess: `train-sim` is ONE
    process, so the K envs step serially on ONE core (Python's GIL). Raising `envs`
    therefore does not buy linear throughput -- it amortises the GPU work over more
    matches, which flattens out. Only the measurement says where.
    """
    cores = int(info.get("cpu_logical") or 8)
    ram = info.get("ram_total") or 0
    vram = info.get("gpu_vram") or 0
    cuda = bool(info.get("cuda_available"))

    envs = max(8, min(48, cores * 2))                     # more envs than cores is fine: they are not threads
    if ram and ram < 8 * 1024 ** 3:
        envs = min(envs, 12)
    batch = 128 if (cuda and vram >= 6 * 1024 ** 3) else 64
    replay = 200_000 if ram >= 24 * 1024 ** 3 else (100_000 if ram >= 12 * 1024 ** 3 else 50_000)
    eval_envs = min(envs, 8)

    candidates = sorted({4, 8, 16, cores, cores * 2, min(64, cores * 4)})
    candidates = [c for c in candidates if 1 <= c <= 96]

    notes = [
        f"{cores} logische CPU-Kerne, "
        f"{(ram / 1024 ** 3):.0f} GB RAM"
        + (f", {info.get('gpu')} mit {(vram / 1024 ** 3):.0f} GB VRAM" if cuda else ", keine nutzbare GPU"),
        "train-sim läuft in EINEM Prozess: die Envs werden nacheinander auf einem Kern gerechnet. "
        "Mehr Envs verteilen die GPU-Arbeit auf mehr Matches, skalieren aber nicht linear: "
        "deshalb misst der Benchmark, statt zu raten.",
    ]
    if not cuda:
        notes.append("Ohne CUDA läuft das Training auf der CPU und ist um ein Vielfaches langsamer. "
                     "Passenden PyTorch-CUDA-Build installieren.")
    return {
        "envs": int(envs), "batch_size": int(batch), "replay_size": int(replay),
        "eval_envs": int(eval_envs), "bench_candidates": candidates,
        "current_envs": int(cur_envs), "notes": notes,
    }
