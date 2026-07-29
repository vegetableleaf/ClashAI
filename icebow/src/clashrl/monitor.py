"""Optional Discord monitor: posts a screenshot of the game window when a long run (e.g.
train-rl) starts, then a short ~30s video CLIP of the window every N minutes, so you can
tell remotely whether the bot is progressing or stuck.

Runs in its OWN background daemon thread with its OWN screen capture, so it keeps posting
even if the training/main thread is blocked -- which is exactly the "is it stuck?" case.

SECURITY: the webhook URL is a secret and is NEVER read from the git-tracked config. It is
read from the environment variable named by ``monitor.webhook_env`` (default
``CLASHRL_DISCORD_WEBHOOK``), or from the git-ignored file ``monitor.webhook_file`` (default
``data/discord_webhook.txt``). If neither is set, the monitor is a no-op.
"""
from __future__ import annotations

import os
import tempfile
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


def _post_file(url: str, data: bytes, filename: str, content_type: str, content: str,
               timeout: float = 60.0) -> None:
    """POST a file (image or video) to a Discord webhook as multipart/form-data (stdlib only)."""
    boundary = uuid.uuid4().hex
    pre = (f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="content"\r\n\r\n{content}\r\n'
           f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
           f"Content-Type: {content_type}\r\n\r\n").encode("utf-8")
    body = pre + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", "clashrl-monitor/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


class DiscordMonitor:
    """Background thread: a screenshot on start, then a short video clip of the game window
    every N minutes."""

    def __init__(self, cfg, label: str = "run"):
        self.cfg = cfg
        self.label = label
        self.interval = max(1.0, float(cfg.get("monitor", "interval_min", default=30.0))) * 60.0
        self.jpg_quality = int(cfg.get("monitor", "jpeg_quality", default=70))
        self.clip_seconds = max(1.0, float(cfg.get("monitor", "clip_seconds", default=30.0)))
        self.clip_fps = max(1, int(cfg.get("monitor", "clip_fps", default=10)))
        self.clip_scale = float(cfg.get("monitor", "clip_scale", default=0.5))
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
        print(f"[monitor] Discord alerts ON: a screenshot now, then a {self.clip_seconds:.0f}s clip "
              f"every {self.interval / 60:.0f} min.")

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        cap = WindowCapture(self.cfg.get("window", "title_contains", default=None),
                            self.cfg.get("window", "region", default=None))
        started = time.time()
        self._send(cap, "monitor started")               # immediate screenshot confirms it works
        while not self._stop.wait(self.interval):
            self._send_clip(cap, f"alive {(time.time() - started) / 3600:.1f}h")

    def _grab(self, cap: WindowCapture):
        """A single window frame, retrying once via a region refresh; None if not found."""
        frame = cap.grab()
        if frame is None:
            cap.refresh_region()
            frame = cap.grab()
        return frame

    def _send(self, cap: WindowCapture, note: str) -> None:
        try:
            frame = self._grab(cap)
            if frame is None:
                print("[monitor] no frame to send (window not found?)")
                return
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpg_quality])
            if not ok:
                return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _post_file(self.url, buf.tobytes(), "screen.jpg", "image/jpeg",
                       f"**{self.label}** — {note} — {ts}")
        except Exception as exc:  # noqa: BLE001 -- monitoring must never break the run
            print(f"[monitor] alert failed (ignored): {exc!r}")

    def _record_clip(self, cap: WindowCapture) -> Optional[bytes]:
        """Capture a ~clip_seconds real-time clip of the game window as mp4 bytes (or None).

        Streams straight to a temp file via cv2.VideoWriter (so it never holds the whole clip
        in RAM), then reads + deletes it. Frames are grabbed at clip_fps and optionally
        downscaled (clip_scale) to keep the upload under Discord's webhook size limit.
        """
        first = self._grab(cap)
        if first is None:
            return None
        if self.clip_scale and self.clip_scale != 1.0:
            first = cv2.resize(first, None, fx=self.clip_scale, fy=self.clip_scale)
        h, w = first.shape[:2]
        tmp = Path(tempfile.gettempdir()) / f"clashrl_clip_{uuid.uuid4().hex}.mp4"
        writer = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), self.clip_fps, (w, h))
        if not writer.isOpened():
            print("[monitor] could not open the mp4 encoder (clip skipped).")
            return None
        dt = 1.0 / self.clip_fps
        try:
            writer.write(first)
            for _ in range(max(1, int(self.clip_seconds * self.clip_fps)) - 1):
                if self._stop.is_set():
                    break
                t0 = time.time()
                f = self._grab(cap)
                if f is not None:
                    writer.write(cv2.resize(f, (w, h)))
                time.sleep(max(0.0, dt - (time.time() - t0)))
        finally:
            writer.release()
        try:
            data = tmp.read_bytes()
        except OSError:
            data = None
        tmp.unlink(missing_ok=True)
        return data

    def _send_clip(self, cap: WindowCapture, note: str) -> None:
        try:
            data = self._record_clip(cap)
            if not data:
                print("[monitor] no clip to send (window not found / encoder failed?)")
                return
            mb = len(data) / (1024 * 1024)
            if mb > 8.0:                       # Discord webhook upload ceiling (no boost) ~8 MiB
                print(f"[monitor] clip is {mb:.1f} MB (> ~8 MB Discord limit); lower "
                      f"monitor.clip_scale / clip_fps / clip_seconds. Sending anyway.")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _post_file(self.url, data, "clip.mp4", "video/mp4",
                       f"**{self.label}** — {note} — {ts}")
        except Exception as exc:  # noqa: BLE001 -- monitoring must never break the run
            print(f"[monitor] clip failed (ignored): {exc!r}")
