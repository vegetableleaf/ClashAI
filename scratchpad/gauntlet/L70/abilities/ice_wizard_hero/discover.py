"""Public-pages-only discovery (Cloudflare clearance, NO login, NO replay fetch): roster + history yield of hero-IW battles."""
import json, sys, time
from pathlib import Path
import crawl_hero_iw as C
from royale import parse
from royale.cookies import Session
from royale.transport import Curl, Pages, AuthError, RateLimited

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
C.OUT.mkdir(exist_ok=True)
pages = Pages()
try:
    curl = Curl(pages, Session("none", ""))      # public pages only; replay endpoint is never called
    ros = C.roster(pages, curl)
    order = sorted(ros["players"], key=lambda t: -int(ros["players"][t].get("rating") or 0))[:N]
    stat, found, types = [], [], {}
    for t in order:
        rows, path = [], f"/player/{t}/battles/history"
        for pg in range(C.PAGES_PER_PLAYER):
            html = C.call(pages, lambda path=path: curl.get(path), "history")
            fresh = parse.battles(html); rows += fresh
            nxt = parse.next_history_page(html)
            if not fresh or not nxt or min(b["battle_timestamp"] for b in fresh) < C.CUTOFF: break
            path = nxt
        for b in rows: types[b["battle_type"]] = types.get(b["battle_type"], 0) + 1
        rec = [b for b in rows if b["battle_timestamp"] >= C.CUTOFF]
        hero = [b for b in rec if C.has_hero(b)]
        rk = [b for b in hero if any(k in b["battle_type"].lower() for k in C.RANKED)]
        found += [{k: b[k] for k in ("replay_tag", "battle_type", "battle_timestamp", "team_deck", "opponent_deck", "result")} | {"player": t} for b in hero]
        stat.append((t, len(rows), len(rec), len(hero), len(rk)))
        print(t, "rows", len(rows), "since-cutoff", len(rec), "hero", len(hero), "ranked-hero", len(rk), flush=True)
    s = [sum(x[i] for x in stat) for i in (1, 2, 3, 4)]
    out = {"players": len(order), "rows": s[0], "since_cutoff": s[1], "hero_either_side": s[2], "ranked_hero": s[3],
           "battle_types": types, "decks_in_roster": len(ros["decks"]), "roster_players": len(ros["players"]),
           "hero_on_player_side": sum(C.HERO in f["team_deck"].split(",") for f in found),
           "hero_only_on_opponent_side": sum(C.HERO not in f["team_deck"].split(",") for f in found)}
    Path(C.OUT / "discovery.json").write_text(json.dumps(out, indent=1))
    Path(C.OUT / "discovered_battles.json").write_text(json.dumps(found))
    print(json.dumps(out, indent=1))
finally:
    pages.close()
