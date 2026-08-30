r"""Post a gauntlet loop report to Discord (stdlib only).

    python tools/gauntlet_report.py --file report.md
    echo "text" | python tools/gauntlet_report.py
    python tools/gauntlet_report.py --file report.md --questions   # marks the run as BLOCKED

/!\ THE WEBHOOK IS A SECRET. It lives in icebow/data/discord_webhook.txt, which is gitignored twice
over (.gitignore data/ + .graphifyignore). This script reads it and NEVER prints it -- not in
errors, not in --dry-run. Do not add a flag that echoes it.

/!\ GIT-BASH curl MANGLES THE PAYLOAD on this box (standing note in memory); use this script, which
goes through urllib, rather than shelling out to curl.

Discord hard-caps a message at 2000 characters, so long reports are split on line boundaries and
posted in order with a part counter. A split mid-code-fence would render broken, so fences are
reopened across parts.
"""
import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEBHOOK = ROOT / "data" / "discord_webhook.txt"
LIMIT = 1900          # under Discord's 2000 so the part header always fits


def _webhook() -> str:
    if not WEBHOOK.exists():
        raise SystemExit("[gauntlet-report] no webhook at %s" % WEBHOOK)
    url = WEBHOOK.read_text(encoding="utf-8").strip()
    if not url.startswith("https://"):
        raise SystemExit("[gauntlet-report] webhook file does not contain an https URL")
    return url


def _chunks(text: str):
    """Split on line boundaries under LIMIT, reopening any code fence left open."""
    out, cur, fence = [], [], False
    for line in text.split("\n"):
        if len("\n".join(cur + [line])) > LIMIT and cur:
            body = "\n".join(cur)
            if fence:
                body += "\n```"
            out.append(body)
            cur = ["```"] if fence else []
        if line.strip().startswith("```"):
            fence = not fence
        cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def post(text: str, dry: bool = False) -> None:
    parts = _chunks(text)
    url = None if dry else _webhook()
    for i, part in enumerate(parts, 1):
        head = "" if len(parts) == 1 else "*(part %d/%d)*\n" % (i, len(parts))
        payload = json.dumps({"content": head + part}).encode("utf-8")
        if dry:
            print("---- part %d/%d (%d chars) ----" % (i, len(parts), len(part)))
            print(part)
            continue
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "clashrl-gauntlet/1.0")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    r.read()
                break
            except urllib.error.HTTPError as e:
                # 429 = rate limited; back off rather than dropping the report
                if e.code == 429 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise SystemExit("[gauntlet-report] HTTP %s posting part %d" % (e.code, i))
            except Exception as e:                              # noqa: BLE001
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise SystemExit("[gauntlet-report] failed part %d: %s" % (i, type(e).__name__))
        time.sleep(0.4)                                          # be polite between parts
    if not dry:
        print("[gauntlet-report] posted %d part(s)" % len(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None, help="read the report from this file (else stdin)")
    ap.add_argument("--questions", action="store_true",
                    help="prefix the report as BLOCKED -- the loop is waiting on the owner")
    ap.add_argument("--dry-run", action="store_true", help="print what would be posted")
    args = ap.parse_args()
    text = pathlib.Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    if args.questions:
        text = "@here **GAUNTLET BLOCKED - waiting on you**\n" + text
    post(text.strip(), dry=args.dry_run)


if __name__ == "__main__":
    main()
