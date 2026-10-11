"""Post a message file to the owner's Discord webhook (URL read from the git-ignored icebow/data/discord_webhook.txt,
never printed). Usage: python post.py <message.txt>   (Discord caps a message at 2000 chars; splits at 1900)."""
import json, sys, urllib.request
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
url = (REPO / "icebow" / "data" / "discord_webhook.txt").read_text(encoding="utf-8").strip()
text = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
try:                                                   # owner 10-10: stage reports in plain words (others unchanged)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fmt import readable
    text = readable(text)
except Exception:                                      # never lose a report to a formatting bug
    pass
chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)] or [""]
for c in chunks:
    req = urllib.request.Request(url, data=json.dumps({"content": c}).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "ClashBot-updates/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        print("posted", len(c), "chars, HTTP", r.status)
