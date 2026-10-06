"""Bounded writer successor around the frozen exact-decision capture hooks.

``count`` counts submitted IDs; ``committed_count`` counts indexed records.
The writer alone owns the frozen disk sink. A three-slot admission semaphore
includes the snapshot currently being collected, both queue slots, and any
writer-owned snapshot. Submission never waits for queue space or disk.

``flush(timeout)`` and ``close(timeout)`` return explicit outcome dictionaries;
writer failures never become policy exceptions. Records use the original NPZ
schema and loader. The original synchronous implementation stays unchanged.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import queue
import sys
import threading
import time


_ORIGINAL = Path(__file__).resolve().parents[1] / "decision_capture" / "capture.py"
_SPEC = importlib.util.spec_from_file_location("_frozen_public_capture_v1_async", _ORIGINAL)
_BASE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _BASE
_SPEC.loader.exec_module(_BASE)

CaptureError = _BASE.CaptureError
load_record = _BASE.load_record
INPUT_KEYS = _BASE.INPUT_KEYS
OUTPUT_KEYS = _BASE.OUTPUT_KEYS

# Each frozen NPZ metadata array is capped at 1 MiB. Every fixed numeric member
# has <=5 dimensions and a short fixed key, so 4 KiB per member exceeds its NPY
# header, ZIP local/central headers and Zip64 extras. 256 KiB reserves a complete
# replacement index (<=128 fixed-size entries). Reservations remain charged for
# the store lifetime, including committed records and possible failed orphans.
METADATA_RESERVE = 1048576
MEMBER_RESERVE = 4096
INDEX_RESERVE = 262144
STATUS_FILE_RESERVE = 4096
STATUS_RESERVE = 2 * STATUS_FILE_RESERVE


class FlushResult(dict):
    """Inspectable outcome with conservative success truth semantics."""
    def __bool__(self):
        return bool(self.get("complete") and self.get("ok") and
                    not self.get("timed_out") and not self.get("disabled_reason"))


def reservation_bytes(meta, arrays):
    """Conservative serialized/disk upper bound; no hashing or serialization."""
    return (sum(int(array.nbytes) for array in arrays.values()) + METADATA_RESERVE +
            (len(arrays) + 1) * MEMBER_RESERVE + INDEX_RESERVE)


class AsyncCaptureStore(_BASE.CaptureStore):
    def __init__(self, directory, manifest, max_records=128, max_bytes=67108864):
        # Exactly one constructor creates the exclusive directory and files.
        self._sink = _BASE.CaptureStore(directory, manifest, max_records, max_bytes)
        self._manifest = self._sink._manifest
        self._manifest_bytes = self._sink._manifest_bytes
        self.manifest_sha256 = self._sink.manifest_sha256
        self.directory = self._sink.directory
        self.max_records, self.max_bytes = max_records, max_bytes
        self.count = 0
        self.timings = []
        self._state_lock = threading.Lock()
        self._decision_lock = threading.Lock()
        self._disabled_reason = None
        self._committed_count = 0
        self._outstanding = 0
        self._reserved_bytes = self._sink._bytes_used + STATUS_RESERVE
        self._writer_failed = False
        self._closed = False
        self._exclusions = []
        self._writer_timings = []
        self._flush_timings = []
        self._queue = queue.Queue(maxsize=2)
        self._slots = threading.BoundedSemaphore(3)
        self._drained = threading.Event()
        self._drained.set()
        self._close_requested = threading.Event()
        self._status_requested = threading.Event()
        self._status_written = False
        self._final_status_written = False
        self._active_token = None
        if self._reserved_bytes > self.max_bytes:
            self._disabled_reason = "initial_reservation_limit"
            self._status_requested.set()
        self._writer = threading.Thread(target=self._writer_loop,
                                        name="public-capture-writer", daemon=True)
        self._writer.start()

    @property
    def disabled_reason(self):
        with self._state_lock:
            return self._disabled_reason

    @property
    def committed_count(self):
        with self._state_lock:
            return self._committed_count

    @property
    def reserved_bytes(self):
        with self._state_lock:
            return self._reserved_bytes

    @property
    def writer_timings(self):
        with self._state_lock:
            return [dict(item) for item in self._writer_timings]

    @property
    def flush_timings(self):
        with self._state_lock:
            return list(self._flush_timings)

    def _disable(self, reason):
        # No printing, file IO, serialization, joins or user callbacks while
        # holding the state mutex or on the instrumented decision path.
        safe = reason if type(reason) is str and len(reason) <= 96 else "capture_error"
        with self._state_lock:
            if self._disabled_reason is None:
                self._disabled_reason = safe
                self._status_requested.set()

    def _snapshot(self):
        with self._state_lock:
            complete = self._outstanding == 0
            return {"complete": complete,
                    "ok": complete and not self._writer_failed and self.count == self._committed_count,
                    "submitted": self.count, "committed": self._committed_count,
                    "pending": self._outstanding, "disabled_reason": self._disabled_reason,
                    "writer_failed": self._writer_failed, "excluded_ids": list(self._exclusions),
                    "reserved_bytes": self._reserved_bytes, "closed": self._closed}

    def _persist_status(self):
        if self._status_written or not self._status_requested.is_set():
            return
        self._status_written = True
        status = {"event": "decision_capture_async_disabled", **self._snapshot()}
        payload = _BASE._json_bytes(status)
        try:
            print(payload.decode("ascii"), file=sys.stderr, flush=True)
        except Exception:
            pass
        # This method runs on the sole writer. The sink's actual-byte budget
        # also includes this file before any subsequent frozen commit.
        if len(payload) <= STATUS_FILE_RESERVE and self._sink._bytes_used + len(payload) <= self.max_bytes:
            try:
                with (self.directory / "async_status.json").open("xb") as stream:
                    stream.write(payload)
                self._sink._bytes_used += len(payload)
            except OSError:
                pass

    def _persist_final_status(self):
        # Preserve the first failure event and a separate terminal outcome.
        # Queued exclusions can accumulate after the first event is written.
        if self._final_status_written:
            return
        self._final_status_written = True
        payload = _BASE._json_bytes({"event": "decision_capture_async_closed", **self._snapshot()})
        if len(payload) <= STATUS_FILE_RESERVE and self._sink._bytes_used + len(payload) <= self.max_bytes:
            try:
                with (self.directory / "async_final_status.json").open("xb") as stream:
                    stream.write(payload)
                self._sink._bytes_used += len(payload)
            except OSError:
                pass

    def decide(self, pilot, frame):
        began = time.perf_counter()
        with self._state_lock:
            bypass = self._closed or self._disabled_reason is not None
        if bypass:
            return pilot.decide(frame)
        if not self._decision_lock.acquire(blocking=False):
            self._disable("concurrent_decision")
            return pilot.decide(frame)
        admitted = False
        token = {"submitted": False}
        base_seconds = 0.0
        prior_timings = len(self.timings)
        try:
            if not self._slots.acquire(blocking=False):
                self._disable("queue_full")
                return pilot.decide(frame)
            admitted = True
            with self._state_lock:
                self._outstanding += 1
                self._drained.clear()
            self._active_token = token
            # Frozen hooks copy only actual calls. Its measured serialization
            # interval becomes validation/submission time in this successor.
            base_started = time.perf_counter()
            try:
                return super().decide(pilot, frame)
            finally:
                base_seconds = time.perf_counter() - base_started
        finally:
            self._active_token = None
            if admitted and not token["submitted"]:
                self._release_snapshot()
            self._decision_lock.release()
            if len(self.timings) == prior_timings + 1:
                added_ms = (time.perf_counter() - began - base_seconds) * 1000
                self.timings[-1]["admission_cleanup_ms"] = added_ms
                self.timings[-1]["total_ms"] += added_ms
                if self.timings[-1]["total_ms"] > 20:
                    self._disable("capture_time_limit")

    def _commit(self, meta, arrays):
        # These arrays are already independent detached copies. Transfer their
        # ownership to the writer without another tensor copy or serialization.
        needed = reservation_bytes(meta, arrays)
        token = self._active_token
        if token is None or token["submitted"]:
            raise CaptureError("invalid capture submission context")
        reason = None
        with self._state_lock:
            if self._closed or self._disabled_reason is not None or self._writer_failed:
                reason = "submission_closed"
            elif self.count >= self.max_records:
                reason = "record_limit"
            elif self._reserved_bytes + needed > self.max_bytes:
                reason = "reservation_byte_limit"
            elif meta["record_id"] != self.count:
                reason = "submission_id_mismatch"
            else:
                # Queue's short mutex protects bookkeeping only; put_nowait
                # never waits for a reader, free capacity or disk completion.
                try:
                    self._queue.put_nowait((self.count, meta, arrays))
                except queue.Full:
                    reason = "queue_full"
                else:
                    self._reserved_bytes += needed
                    self.count += 1
                    token["submitted"] = True
        if reason is not None:
            self._disable(reason)
            raise CaptureError("capture submission rejected")

    def _write_record(self, meta, arrays):
        """Single-writer seam for bounded failure/backpressure qualification."""
        _BASE.CaptureStore._commit(self._sink, meta, arrays)

    def _release_snapshot(self):
        with self._state_lock:
            self._outstanding -= 1
            if self._outstanding == 0:
                self._drained.set()
        self._slots.release()

    def _write_item(self, item):
        record_id, meta, arrays = item
        started = time.perf_counter()
        with self._state_lock:
            failed = self._writer_failed
        error_code = None
        if not failed:
            try:
                if record_id != self._sink.count or meta["record_id"] != record_id:
                    raise CaptureError("writer ordering")
                self._write_record(meta, arrays)
            except Exception as error:
                error_code = "writer_" + type(error).__name__
                with self._state_lock:
                    self._writer_failed = True
                self._disable(error_code)
        with self._state_lock:
            self._committed_count = self._sink.count
            committed = record_id < self._committed_count
            if not committed:
                self._exclusions.append(record_id)
            self._writer_timings.append({"record_id": record_id,
                                         "write_ms": (time.perf_counter() - started) * 1000,
                                         "committed": committed, "excluded": not committed,
                                         "error": error_code or ("prior_writer_failure" if failed else None)})

    def _writer_loop(self):
        while True:
            self._persist_status()
            if self._close_requested.is_set() and self._queue.empty() and self._snapshot()["complete"]:
                self._persist_final_status()
                return
            try:
                item = self._queue.get(timeout=.05)
            except queue.Empty:
                continue
            try:
                self._write_item(item)
            finally:
                # Drop the snapshot before releasing its admission slot. This
                # includes the writer's local reference and _write_item frame.
                item = None
                self._queue.task_done()
                self._release_snapshot()

    @staticmethod
    def _timeout(value):
        if type(value) not in (int, float) or not 0 <= value <= 60:
            raise ValueError("timeout must be between zero and sixty seconds")
        return float(value)

    def flush(self, timeout=5.0):
        timeout = self._timeout(timeout)
        started = time.perf_counter()
        drained = self._drained.wait(timeout)
        result = self._snapshot()
        result["timed_out"] = not drained or not result["complete"]
        result["flush_ms"] = (time.perf_counter() - started) * 1000
        with self._state_lock:
            if len(self._flush_timings) < 256:
                self._flush_timings.append(result["flush_ms"])
        return FlushResult(result)

    def close(self, timeout=5.0):
        timeout = self._timeout(timeout)
        started = time.perf_counter()
        with self._state_lock:
            self._closed = True
        self._close_requested.set()
        result = self.flush(timeout)
        remaining = max(0.0, timeout - (time.perf_counter() - started))
        self._writer.join(remaining)
        result = {**result, **self._snapshot(), "writer_alive": self._writer.is_alive()}
        result["timed_out"] = not result["complete"] or result["writer_alive"]
        result["close_ms"] = (time.perf_counter() - started) * 1000
        return FlushResult(result)
