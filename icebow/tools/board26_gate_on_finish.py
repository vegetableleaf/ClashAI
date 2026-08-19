"""Wait for board-26 to finish, then run the HONEST gate on it and report the verdict.

Why this exists as a detached script rather than a monitor: the gate is the only thing that
decides whether a detector generation replaces the pin (HANDOFF SS6.3), it takes ~4 minutes per
generation, and board-26 finishes at an unpredictable hour. Leaving a human a command to run means
the answer waits for them; this produces the answer.

It runs `detect-eval` on BOTH board-26's final best.pt and the incumbent board-24-5, over the same
frozen 241-image live subset (data/detect/val_board15.txt, verified 0% Roboflow), because the
comparison is the point -- board-26's own val set is 81% Roboflow images the older run never saw,
so its training-time mAP is not comparable (HANDOFF SS8).

Usage:  python tools/board26_gate_on_finish.py [--timeout-h 8] [--no-discord]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "detect" / "board-26"
LOG = ROOT / "runs" / "board26_resume.out"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
SUBSET = "data/detect/val_board15.txt"
INCUMBENT = "runs/detect/board-24-5/weights/best.pt"
CHALLENGER = "runs/detect/board-26/weights/best.pt"
WEBHOOK = ROOT / "data" / "discord_webhook.txt"


def epochs_done() -> int:
    try:
        return max(0, sum(1 for _ in RUN.joinpath("results.csv").open(encoding="utf-8")) - 1)
    except OSError:
        return 0


def finished() -> bool:
    """Training is done when ultralytics says so, or the log has gone quiet for 20 minutes."""
    try:
        txt = LOG.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if "epochs completed in" in txt or "EarlyStopping" in txt:
        return True
    if epochs_done() >= 120:
        return True
    try:
        return (time.time() - LOG.stat().st_mtime) > 1200
    except OSError:
        return False


def gate(weights: str) -> tuple[str, dict]:
    """Run detect-eval and pull out the numbers that decide the pin."""
    out = subprocess.run(
        [str(PY), "run.py", "detect-eval", "--weights", weights, "--subset", SUBSET],
        cwd=str(ROOT), capture_output=True, text=True, timeout=3600).stdout
    got: dict = {}
    m = re.search(r"presence UNITS\s+([\d.]+)\s+vs\s+([\d.]+)\s+(\w+)", out)
    if m:
        got["presence"], got["presence_gate"], got["presence_verdict"] = \
            float(m.group(1)), float(m.group(2)), m.group(3)
    m = re.search(r"whitelist ident\s+([\d.]+)\s+vs\s+([\d.]+)\s+(\w+)", out)
    if m:
        got["whitelist"], got["whitelist_verdict"] = float(m.group(1)), m.group(3)
    m = re.search(r"deck UNITS\s+(\d+)/(\d+)", out)
    if m:
        got["deck_ok"], got["deck_total"] = int(m.group(1)), int(m.group(2))
    got["deck_rows"] = {c: float(r) for c, r in
                        re.findall(r"^\s+(\w+)\s+R ([\d.]+)\s+\(n=\d+\)", out, re.M)}
    return out, got


def post(text: str) -> None:
    try:
        url = WEBHOOK.read_text(encoding="utf-8").strip()
    except OSError:
        print("[gate] no webhook file; skipping Discord")
        return
    for chunk in [text[i:i + 1900] for i in range(0, len(text), 1900)]:
        body = json.dumps({"content": chunk, "allowed_mentions": {"parse": []}}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json",
                     "User-Agent": "ClashBot-gate/1.0 (+github vegetableleaf/ClashAI)"})
        try:
            with urllib.request.urlopen(req, timeout=30):
                pass
        except Exception as exc:            # noqa: BLE001 - never echo the webhook
            print("[gate] discord post failed: %s" % type(exc).__name__)
            return
        time.sleep(0.6)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-h", type=float, default=8.0)
    ap.add_argument("--no-discord", action="store_true")
    ap.add_argument("--now", action="store_true", help="skip the wait (for testing)")
    a = ap.parse_args(argv)

    deadline = time.time() + a.timeout_h * 3600
    while not a.now and not finished():
        if time.time() > deadline:
            print("[gate] timed out waiting for board-26 (epoch %d)" % epochs_done())
            return 1
        time.sleep(120)

    n = epochs_done()
    print("[gate] board-26 finished at epoch %d; running the honest gate on both generations" % n)
    ch_out, ch = gate(CHALLENGER)
    in_out, inc = gate(INCUMBENT)
    (ROOT / "runs" / "gate_board26.txt").write_text(ch_out, encoding="utf-8")
    (ROOT / "runs" / "gate_board24_5.txt").write_text(in_out, encoding="utf-8")

    # The pin only moves if the challenger is at least as good on BOTH headline gates and does not
    # lose a deck card. Presence recall is the obs-canvas flip gate, so it is the one that counts.
    better = (ch.get("presence", 0) >= inc.get("presence", 1)
              and ch.get("whitelist", 0) >= inc.get("whitelist", 1)
              and ch.get("deck_ok", 0) >= inc.get("deck_ok", 9))
    lines = [
        "## 🎯 board-26 finished at epoch %d — the honest gate (241 live images, 0%% Roboflow)" % n,
        "",
        "| metric | board-24-5 (pin) | board-26 |",
        "|---|---|---|",
        "| presence UNITS recall | %.3f | %.3f |" % (inc.get("presence", 0), ch.get("presence", 0)),
        "| whitelist identity | %.3f | %.3f |" % (inc.get("whitelist", 0), ch.get("whitelist", 0)),
        "| deck units passing | %s/%s | %s/%s |" % (inc.get("deck_ok", "?"), inc.get("deck_total", "?"),
                                                    ch.get("deck_ok", "?"), ch.get("deck_total", "?")),
        "",
    ]
    rows = sorted(set(ch.get("deck_rows", {})) | set(inc.get("deck_rows", {})))
    if rows:
        lines.append("Per deck card (recall):")
        lines.append("```")
        for c in rows:
            i_v, c_v = inc.get("deck_rows", {}).get(c), ch.get("deck_rows", {}).get(c)
            if i_v is None or c_v is None:
                continue
            flag = "  <-- worse" if c_v < i_v - 0.001 else ("  better" if c_v > i_v + 0.001 else "")
            lines.append("  %-14s %.2f -> %.2f%s" % (c, i_v, c_v, flag))
        lines.append("```")
    lines += [
        "",
        ("**VERDICT: board-26 WINS — it may replace the pin.** Flip `detect.weights` to "
         "`runs/detect/board-26/weights/best.pt` in both decks' config." if better else
         "**VERDICT: board-26 does NOT beat the pin.** `detect.weights` stays on board-24-5. "
         "Its training-time mAP lead is its own val set (81% Roboflow), which is exactly the "
         "trap HANDOFF §8 records."),
        "",
        "Full output: `icebow/runs/gate_board26.txt` and `gate_board24_5.txt`.",
    ]
    report = "\n".join(lines)
    print(report)
    if not a.no_discord:
        post(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
