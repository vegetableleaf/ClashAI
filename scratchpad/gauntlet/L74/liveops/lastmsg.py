"""Print the final agent message of a Codex --json event file (utf-8 safe). Usage: python lastmsg.py OUT.jsonl"""
import json, sys
msgs = []
for l in open(sys.argv[1], encoding="utf-8", errors="replace"):
    try:
        e = json.loads(l)
    except ValueError:
        continue
    it = e.get("item") or {}
    if it.get("type") == "agent_message":
        msgs.append(it.get("text", ""))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
print(msgs[-1] if msgs else "NO FINAL MESSAGE")
