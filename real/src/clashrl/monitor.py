"""Optional Discord monitor: periodically posts a screenshot of the game window to a
Discord webhook while a long run (e.g. train-rl) is going, so you can tell remotely
whether the bot is progressing or stuck.

Runs in its OWN background daemon thread with its OWN screen capture, so it keeps posting
even if the training/main thread is blocked -- which is exactly the "is it stuck?" case.

SECURITY: the webhook URL is a secret and is NEVER read from the git-tracked config. It is
read from the environment variable named by ``monitor.webhook_env`` (default
``CLASHRL_DISCORD_WEBHOOK``), or from the git-ignored file ``monitor.webhook_file`` (default
``data/discord_webhook.txt``). If neither is set, the monitor is a no-op.
"""
from __future__ import annotations

import os
import threading
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

from .capture import WindowCapture


def _load_webhook(cfg) -> Optional[str]:
    """The Discord webhook URL from the env var (preferred) or the git-ignored file, or None."""
    env_name = cfg.get("monitor", "webhook_env", default="CLASHRL_DISCORD_WEBHOOK")
    url = os.environ.get(env_name) if env_name else None
    if url and url.strip():
        return url.strip()
    fpath = cfg.get("monitor", "webhook_file", default="data/discord_webhook.txt")
    p = Path(cfg.path(fpath))
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def _post_screenshot(url: str, jpg: bytes, content: str, timeout: float = 15.0) -> None:
    """POST a JPEG to a Discord webhook as multipart/form-data (stdlib only, no requests)."""
    boundary = uuid.uuid4().hex
    pre = (f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="content"\r\n\r\n{content}\r\n'
           f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="file"; filename="screen.jpg"\r\n'
           f"Content-Type: image/jpeg\r\n\r\n").encode("utf-8")
    body = pre + jpg + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", "clashrl-monitor/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


class DiscordMonitor:
    """Background thread that posts a game-window screenshot to Discord every N minutes."""

    def __init__(self, cfg, label: str = "run"):
        self.cfg = cfg
        self.label = label
        self.interval = max(1.0, float(cfg.get("monitor", "interval_min", default=30.0))) * 60.0
        self.jpg_quality = int(cfg.get("monitor", "jpeg_quality", default=70))
        self.url = _load_webhook(cfg)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if not self.url:
            env_name = self.cfg.get("monitor", "webhook_env", default="CLASHRL_DISCORD_WEBHOOK")
            wfile = self.cfg.get("monitor", "webhook_file", default="data/discord_webhook.txt")
            print(f"[monitor] Discord alerts OFF (no webhook configured). To enable, set env "
                  f"{env_name} or put the webhook URL in the git-ignored file {wfile}.")
            return
        self._thread = threading.Thread(target=self._run, name="discord-monitor", daemon=True)
        self._thread.start()
        print(f"[monitor] Discord alerts ON: a screenshot every {self.interval / 60:.0f} min.")

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        cap = WindowCapture(self.cfg.get("window", "title_contains", default=None),
                            self.cfg.get("window", "region", default=None))
        started = time.time()
        self._send(cap, "monitor started")               # immediate post confirms it works
        while not self._stop.wait(self.interval):
            self._send(cap, f"alive {(time.time() - started) / 3600:.1f}h")

    def _send(self, cap: WindowCapture, note: str) -> None:
        try:
            frame = cap.grab()
            if frame is None:
                cap.refresh_region()
                frame = cap.grab()
            if frame is None:
                print("[monitor] no frame to send (window not found?)")
                return
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpg_quality])
            if not ok:
                return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _post_screenshot(self.url, buf.tobytes(), f"**{self.label}** — {note} — {ts}")
        except Exception as exc:  # noqa: BLE001 -- monitoring must never break the run
            print(f"[monitor] alert failed (ignored): {exc!r}")
