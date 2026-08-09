"""Stop-signal shim for CLI processes launched by the UI.

Windows cannot deliver a real Ctrl+C to another process group: `CTRL_C_EVENT` is
DISABLED in children created with `CREATE_NEW_PROCESS_GROUP` (which we need, so a
stop never hits the UI server itself). The only signal that gets through is
`CTRL_BREAK_EVENT` -> `SIGBREAK`, and Python's default SIGBREAK action kills the
process outright -- skipping every `except KeyboardInterrupt` / `finally: save()`
path the training commands rely on to checkpoint on exit.

So the UI sets `CLASHRL_UI_CHILD=1` and `cli.main()` calls `install_stop_signal()`,
which maps SIGBREAK onto the ordinary Ctrl+C path. Guarded by that env var, so the
CLI's behaviour outside the UI is byte-for-byte unchanged.

Note the commands install their own SIGINT handlers (train_sim flips a `running`
flag, play/train_rl re-raise); SIGBREAK is a separate slot, so ours survives and
raises KeyboardInterrupt in the main thread -- which every long-running command
already catches and answers with a save.
"""
from __future__ import annotations

import signal


def install_stop_signal() -> None:
    """Map the UI's stop signal onto KeyboardInterrupt (no-op where unsupported)."""
    sigbreak = getattr(signal, "SIGBREAK", None)          # Windows only
    if sigbreak is None:
        return

    def _stop(_signum, _frame):
        raise KeyboardInterrupt

    try:
        signal.signal(sigbreak, _stop)
    except (ValueError, OSError):                          # not the main thread / no console
        pass
