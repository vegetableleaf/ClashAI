"""One-replay verification fetch: does an 'uncovered' replay ship .marker elements with data-i=1?
Read-only on data; payload saved under scratchpad. No interactive login: exits if no session."""
import sys, csv, json, collections
from pathlib import Path
sys.path.insert(0, "C:/Users/benpe/clash-replay-scraper")
from royale.cookies import Session, find_sessions
from royale.transport import ClearanceExpired, Curl, Pages
from royale import pipeline
from bs4 import BeautifulSoup

OUT = Path("C:/Users/benpe/ClashBot/icebow/data/royaleapi/crawl2")
DST = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L64/xy_why/refetch")
tags = sys.argv[1:] or ["00YYPYJ2GPUU"]

pages = Pages()
curl = None
try:
    for cand in find_sessions():
        c = Curl(pages, cand)
        try:
            if c.logged_in():
                curl = c; print("[probe] session: jar", flush=True); break
        except ClearanceExpired:
            pages.renew()
    tok = OUT / ".session_token"
    if curl is None and tok.exists():
        c = Curl(pages, Session("saved", tok.read_text(encoding="utf-8").strip()))
        for att in range(3):
            try:
                if c.logged_in():
                    curl = c; print("[probe] session: saved token", flush=True)
                break
            except ClearanceExpired:
                pages.renew()
    if curl is None:
        print("NO_SESSION", flush=True); sys.exit(2)
    rows = {r["replay_tag"]: r for r in csv.DictReader(open(OUT / "battles.csv", encoding="utf-8"))}
    for tag in tags:
        b = rows[tag]
        data = curl.json("/data/replay", pipeline.replay_params(b))
        if not data.get("success"):
            print("REFUSED", tag, flush=True); continue
        html = data["html"]
        (DST / f"{tag}.html").write_text(html, encoding="utf-8")
        d = BeautifulSoup(html, "lxml")
        ms = d.select(".marker")
        cards = d.select(".replay_timeline .replay_card")
        ci = collections.Counter((m.get("data-i"), m.get("data-s")) for m in ms)
        ys = collections.defaultdict(list)
        for m in ms:
            try: ys[(m.get("data-i"), m.get("data-s"))].append(int(m.get("data-y")) / 1000.0)
            except (TypeError, ValueError): pass
        med = {str(k): (round(sorted(v)[len(v)//2], 1), len(v)) for k, v in ys.items()}
        print(json.dumps({"tag": tag, "cards": len(cards), "markers": len(ms),
                          "by_i_s": {str(k): v for k, v in ci.items()}, "median_tile_y_by_i_s": med,
                          "sample": [dict(m.attrs) for m in ms[:3]]}), flush=True)
finally:
    pages.close()
