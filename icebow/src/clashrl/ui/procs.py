"""Start / stream / stop CLI subprocesses for the UI.

One `Job` == one `run.py <cmd>` process. stdout is streamed line-by-line to every
SSE subscriber, mirrored to `data/ui_logs/<job>.log`, and scraped for metrics.

Stopping is a GRACEFUL stop, not a kill: the commands checkpoint in their
`except KeyboardInterrupt` / `finally` blocks, so the UI sends the signal that
reaches those paths (Ctrl+Break on Windows -> `ui.child.install_stop_signal`,
SIGINT elsewhere) and only escalates to terminate/kill if the process ignores it.
"""
from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import jobs as jobcat
from .metrics import MetricsStore, parse_line

_IS_WIN = os.name == "nt"
LOG_LINES = 4000                      # in-memory tail per job (the full log is on disk)


class Job:
    def __init__(self, jid: str, cmd: str, argv: List[str], log_path: Path, gpu: bool):
        self.id = jid
        self.cmd = cmd
        self.argv = argv
        self.gpu = gpu
        self.log_path = log_path
        self.started = time.time()
        self.finished: Optional[float] = None
        self.rc: Optional[int] = None
        self.stopping = False
        self.track_metrics = False                       # set from the catalog at spawn time
        self.proc: Optional[subprocess.Popen] = None
        self.lines: deque = deque(maxlen=LOG_LINES)
        self.seq = 0                                     # monotonic line counter (client resync)
        self._subs: List[queue.Queue] = []
        self._lock = threading.Lock()

    # -- fan-out ---------------------------------------------------------
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def _emit(self, line: str) -> None:
        with self._lock:
            self.seq += 1
            self.lines.append(line)
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(line)
            except queue.Full:                            # a stalled browser tab must not stall the reader
                pass

    # -- state -----------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def info(self) -> Dict[str, Any]:
        return {"id": self.id, "cmd": self.cmd, "argv": self.argv, "gpu": self.gpu,
                "started": self.started, "finished": self.finished, "rc": self.rc,
                "running": self.running, "stopping": self.stopping,
                "pid": self.proc.pid if self.proc else None,
                "elapsed": (self.finished or time.time()) - self.started,
                "log": str(self.log_path)}


class ProcManager:
    def __init__(self, root: Path, metrics: MetricsStore, python: Optional[str] = None):
        self.root = Path(root)                            # icebow/
        self.metrics = metrics
        self.python = python or sys.executable
        self.jobs: Dict[str, Job] = {}
        self.order: List[str] = []
        self._lock = threading.Lock()
        self.log_dir = self.root / "data" / "ui_logs"

    # -- queries ---------------------------------------------------------
    def active(self) -> List[Job]:
        return [j for j in self.jobs.values() if j.running]

    def gpu_busy(self) -> Optional[Job]:
        for j in self.active():
            if j.gpu:
                return j
        return None

    def list(self) -> List[Dict[str, Any]]:
        return [self.jobs[i].info() for i in reversed(self.order) if i in self.jobs][:40]

    # -- lifecycle -------------------------------------------------------
    def start(self, cmd: str, values: Dict[str, Any]) -> Job:
        spec = jobcat.BY_CMD.get(cmd)
        if spec is None:
            raise jobcat.ArgError(f"unbekanntes Kommando: {cmd}")
        argv_tail = jobcat.build_argv(cmd, values)
        with self._lock:
            if spec["gpu"]:
                busy = self.gpu_busy()
                if busy is not None:
                    raise RuntimeError(
                        f"'{busy.cmd}' läuft bereits und belegt GPU/Fenster. "
                        f"Erst stoppen, dann '{cmd}' starten.")
            if any(j.cmd == cmd for j in self.active()):
                raise RuntimeError(f"'{cmd}' läuft bereits.")
            jid = f"{cmd}-{time.strftime('%Y%m%d-%H%M%S')}"
            if jid in self.jobs:                          # same second, same command
                jid += f"-{len(self.jobs)}"
            self.log_dir.mkdir(parents=True, exist_ok=True)
            job = Job(jid, cmd, argv_tail, self.log_dir / f"{jid}.log", bool(spec["gpu"]))
            self.jobs[jid] = job
            self.order.append(jid)

        env = dict(os.environ)
        env["CLASHRL_UI_CHILD"] = "1"                     # arms the Ctrl+Break -> KeyboardInterrupt shim
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cmdline = [self.python, "-u", str(self.root / "run.py")] + argv_tail
        creation = subprocess.CREATE_NEW_PROCESS_GROUP if _IS_WIN else 0
        job.proc = subprocess.Popen(
            cmdline, cwd=str(self.root), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=creation, start_new_session=(not _IS_WIN),
        )
        job._emit(f"$ {' '.join(cmdline)}")
        job.track_metrics = bool(spec.get("metrics"))     # only training runs belong in the dashboard
        if job.track_metrics:
            target = None
            for a in spec["args"]:
                if a["name"] == "matches":
                    target = values.get("matches") or a.get("default")
            self.metrics.append({"kind": "run_start", "run": job.id, "cmd": cmd,
                                 "argv": argv_tail, "target_matches": _as_int(target)})
        threading.Thread(target=self._pump, args=(job,), daemon=True,
                         name=f"pump-{job.id}").start()
        return job

    def _pump(self, job: Job) -> None:
        """Read the child's stdout to EOF: fan out, persist, scrape metrics."""
        assert job.proc is not None
        try:
            with open(job.log_path, "a", encoding="utf-8") as logf:
                logf.write(f"$ {' '.join([self.python, '-u', 'run.py'] + job.argv)}\n")
                for raw in job.proc.stdout:               # type: ignore[union-attr]
                    line = raw.rstrip("\n").rstrip("\r")
                    job._emit(line)
                    logf.write(line + "\n")
                    logf.flush()
                    rec = parse_line(line) if job.track_metrics else None
                    if rec is not None:
                        rec["run"] = job.id
                        rec.setdefault("cmd", job.cmd)
                        try:
                            self.metrics.append(rec)
                        except OSError:
                            pass
        except Exception as exc:                          # noqa: BLE001 -- reader must never take the UI down
            job._emit(f"[ui] Log-Reader abgebrochen: {exc}")
        finally:
            job.rc = job.proc.wait()
            job.finished = time.time()
            secs = job.finished - job.started
            # 130 = our own clean Ctrl+C exit, 0xC000013A = Windows' control-C exit code.
            # After a stop those mean "did what it was told", not "crashed".
            if job.stopping and job.rc in (0, 130, 3221225786, -1073741510):
                job._emit(f"[ui] gestoppt und beendet nach {secs:.0f}s")
            else:
                job._emit(f"[ui] beendet (Exit-Code {job.rc}) nach {secs:.0f}s")
            if job.track_metrics:
                self.metrics.append({"kind": "run_end", "run": job.id, "cmd": job.cmd, "rc": job.rc})

    def stop(self, jid: str, grace: float = 30.0) -> Dict[str, Any]:
        job = self.jobs.get(jid)
        if job is None:
            raise KeyError(jid)
        if not job.running:
            return job.info()
        job.stopping = True
        job._emit("[ui] Stop-Signal gesendet. Ein laufendes Training speichert dabei seinen Stand; "
                  "wird noch gestartet, bricht es einfach ab.")
        try:
            if _IS_WIN:
                os.kill(job.proc.pid, signal.CTRL_BREAK_EVENT)   # type: ignore[union-attr]
            else:
                job.proc.send_signal(signal.SIGINT)               # type: ignore[union-attr]
        except (OSError, ValueError) as exc:
            job._emit(f"[ui] Stop-Signal fehlgeschlagen ({exc}) -- beende hart.")
            job.proc.terminate()                                  # type: ignore[union-attr]
        threading.Thread(target=self._escalate, args=(job, grace), daemon=True).start()
        return job.info()

    def _escalate(self, job: Job, grace: float) -> None:
        """Give the child time to checkpoint, then force it down."""
        deadline = time.time() + grace
        while time.time() < deadline:
            if not job.running:
                return
            time.sleep(0.3)
        if job.running:
            job._emit(f"[ui] nach {grace:.0f}s nicht beendet -- terminate()")
            try:
                job.proc.terminate()                              # type: ignore[union-attr]
            except OSError:
                pass
        time.sleep(5.0)
        if job.running:
            job._emit("[ui] reagiert weiterhin nicht -- kill()")
            try:
                job.proc.kill()                                   # type: ignore[union-attr]
            except OSError:
                pass

    def stop_all(self, grace: float = 30.0) -> None:
        for j in self.active():
            try:
                self.stop(j.id, grace=grace)
            except Exception:                                     # noqa: BLE001
                pass


def _as_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
