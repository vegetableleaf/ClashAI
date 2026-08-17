"""Ping Discord when train-sim-ppo banks a new best.

    python tools/ppo_best_ping.py data/ppo_fundamentals.log

Follows the run's log and posts every `new BEST ladder avg` line. Tails from the END by default,
so restarting the watcher does not re-announce bests that already happened.

The webhook is a SECRET: read from data/discord_webhook.txt (git-ignored), never printed, never
echoed into an error message. Posted with urllib -- Git-Bash curl mangles the URL on this box.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MARK = "new BEST ladder avg"


def _webhook() -> str:
    p = _ROOT / "data" / "discord_webhook.txt"
    if not p.exists():
        raise SystemExit("no data/discord_webhook.txt")
    return p.read_text(encoding="utf-8").strip()


def _post(url: str, text: str) -> None:
    body = json.dumps({"content": text}).encode()
    # THE USER-AGENT IS NOT OPTIONAL. Discord answers 403 Forbidden to urllib's default
    # "Python-urllib/3.x" -- verified against this webhook. Without it every ping would have
    # failed silently behind the except below, and the watcher would have looked healthy while
    # announcing nothing.
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "icebow-monitor/1.0 (+local)"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:  # noqa: BLE001
        # Never let the URL reach a log line. Report the failure TYPE only.
        print("[ping] post failed: %s %s" % (type(e).__name__, getattr(e, "code", "")), flush=True)


def main(argv) -> int:
    log = Path(argv[0]) if argv else (_ROOT / "data" / "ppo_fundamentals.log")
    if not log.is_absolute():
        log = _ROOT / log
    url = _webhook()
    from_start = "--from-start" in argv
    print("[ping] watching %s for %r" % (log.name, _MARK), flush=True)

    pos = 0
    if log.exists() and not from_start:
        pos = log.stat().st_size
    seen = 0
    while True:
        try:
            if log.exists():
                size = log.stat().st_size
                if size < pos:                 # truncated / rotated -> start over
                    pos = 0
                if size > pos:
                    with log.open("r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(pos)
                        chunk = fh.read()
                        pos = fh.tell()
                    for line in chunk.splitlines():
                        if _MARK in line:
                            seen += 1
                            _post(url, ":trophy: **PPO new best** — `%s`\n%s"
                                       % (log.name, line.strip()))
                            print("[ping] announced: %s" % line.strip(), flush=True)
        except Exception as e:  # noqa: BLE001
            print("[ping] read failed: %s" % type(e).__name__, flush=True)
        time.sleep(20)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
