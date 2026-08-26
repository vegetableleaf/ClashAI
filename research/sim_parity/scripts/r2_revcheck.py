# -*- coding: utf-8 -*-
"""Check whether a vardefine was updated for a dated balance change:
list recent revisions of a page, then fetch the wikitext of a pre-date revision
and print the requested vardefines then vs now."""
import json, time, re, urllib.request, urllib.parse, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
HDRS = {"User-Agent": "icebow-monitor/1.0 (+local)"}

def api(params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(BASE + "?" + qs, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    time.sleep(0.25)
    return data

title = sys.argv[1]
cutoff = sys.argv[2]          # ISO date like 2026-04-06: find last revision BEFORE this
varnames = sys.argv[3].split(",")

d = api({"action":"query","prop":"revisions","titles":title,
         "rvprop":"ids|timestamp|comment","rvlimit":"50","format":"json"})
pages = d["query"]["pages"]
revs = list(pages.values())[0]["revisions"]
print("RECENT REVISIONS:")
for r in revs[:50]:
    print(f'  {r["revid"]}  {r["timestamp"]}  {r.get("comment","")[:90]}')
older = [r for r in revs if r["timestamp"] < cutoff+"T00:00:00Z"]
if not older:
    print(f"NO revision older than {cutoff} in the last 50; oldest shown above")
    sys.exit(0)
old = older[0]
print(f'\nLAST PRE-{cutoff} REVISION: {old["revid"]} @ {old["timestamp"]}')
d2 = api({"action":"parse","oldid":old["revid"],"prop":"wikitext","format":"json"})
wt = d2["parse"]["wikitext"]["*"]
print("VARDEFINES THEN:")
for m in re.finditer(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}", wt):
    if not varnames or m.group(1).strip() in varnames or varnames==["ALL"]:
        print(f"  {m.group(1)} = {m.group(2)}")
