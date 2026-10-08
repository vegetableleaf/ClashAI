"""One long-lived `adb shell` for in-match inputs (live_play.py --fast-input; L74 latency, 2026-10-08).

live_play's default spawns adb.exe once per input (`adb shell "input tap ..; sleep 0.05; input tap .."`): tap_ms
median 151 over 6,530 live plays, of which ~73 ms is spawning adb.exe alone (adb.exe version, measured on this laptop
under live load; scratchpad/gauntlet/L74/latency/adb_spawn_local.txt). Here one `adb shell` stays open; each command is
written to its stdin followed by `echo <marker>`, and run() returns when the marker comes back (the same "the device
finished the command" point the per-call path returns at). The commands themselves are unchanged.

Timeout semantics match live_play.input_cmd: False = no marker in time (the command may still run on the device
later); the shell is then killed and the next call starts a new one.

Owner self-test (no input is ever sent; only `true`; run between matches, not during one):
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/fast_input.py --selftest
"""
from __future__ import annotations

import queue
import subprocess
import threading
import time


class PersistentShell:
    def __init__(self, adb: list[str], env: dict | None = None):
        self.adb, self.env, self.p, self.lines, self.n = list(adb), env, None, None, 0

    def _start(self) -> None:
        # bytes, unbuffered: a text-mode pipe on Windows would send "\r\n" to the device shell
        self.p = subprocess.Popen(self.adb + ["shell"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, bufsize=0, env=self.env)
        self.lines = queue.Queue()
        threading.Thread(target=self._pump, args=(self.p, self.lines), daemon=True).start()

    @staticmethod
    def _pump(p, lines) -> None:
        for ln in p.stdout:
            lines.put(ln)
        lines.put(None)                                   # the shell exited

    def run(self, cmd: str, timeout: float = 5.0) -> bool:
        """Run one shell command line; True once the device finished it, False on timeout / a dead shell."""
        t_end = time.monotonic() + timeout
        try:
            if self.p is None or self.p.poll() is not None:
                self._start()
            self.n += 1
            marker = f"__fi{self.n}__".encode()
            self.p.stdin.write(f"{cmd}; echo {marker.decode()}\n".encode())
            while True:
                ln = self.lines.get(timeout=max(0.0, t_end - time.monotonic()))
                if ln is None:                            # shell died before the marker
                    self.close()
                    return False
                if ln.strip() == marker:
                    return True
        except (queue.Empty, OSError, ValueError):
            self.close()                                  # never reuse a shell whose output is out of step
            return False

    def close(self) -> None:
        p, self.p = self.p, None
        if p is None:
            return
        try:
            p.stdin.close()                               # EOF -> the device shell exits after its last command
        except OSError:
            pass
        try:
            p.wait(timeout=1)
        except subprocess.TimeoutExpired:
            p.kill()


def selftest(n: int = 20) -> None:
    """Round-trip of a no-op (`true`) through the persistent shell vs one adb.exe per call. Sends NO input."""
    import statistics
    from live_play import ADB, ENV, adb
    sh = PersistentShell(ADB, ENV)
    per, pers = [], []
    for _ in range(n):
        t = time.perf_counter()
        adb("shell", "true")
        per.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        ok = sh.run("true")
        pers.append((time.perf_counter() - t) * 1000 if ok else float("nan"))
    sh.close()
    print(f"adb.exe per call   median {statistics.median(per):.1f} ms  {sorted(round(x) for x in per)}")
    print(f"persistent shell   median {statistics.median(pers):.1f} ms  {sorted(round(x) for x in pers)}"
          f"  (first call includes the one-time shell start)")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        selftest()
    else:
        print(__doc__)
