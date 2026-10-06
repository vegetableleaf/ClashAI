"""Hero-Ice-Wizard crawl (copy-adapted from clash-replay-scraper/crawl_deck.py, which is read-only here).

Keeps a battle when EITHER deck holds `ice-wizard-hero`. Sequential, the crawler's Limiter pacing.
Cloudflare: any renewal that cannot finish on its own => write BLOCKED and exit 3 (never click/bypass).
Session token: read in memory from an existing crawl's .session_token; NEVER written to this folder.
Resume-safe: players_done.json, replays_done.json, battles.csv / plays.csv / payloads/ in crawl/.
Run:  python crawl_hero_iw.py [--target-deploys 500] [--max-hours 3]
"""
import argparse, csv, datetime as dt, gzip, json, re, sys, time
from pathlib import Path

sys.path.insert(0, "C:/Users/benpe/clash-replay-scraper")
from royale import parse, pipeline                                   # noqa: E402
from royale.cookies import Session                                   # noqa: E402
from royale.transport import AuthError, ClearanceExpired, Curl, Pages, RateLimited  # noqa: E402
from crawl_deck import parse_replay_ext                              # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "crawl"
HERO = "ice-wizard-hero"
SEED = "ice-wizard-hero,knight-ev1,rocket,skeletons,tesla-ev1,the-log,tornado,x-bow"
TOKENS = ["C:/Users/benpe/ClashBot/icebow/data/royaleapi/crawl2/.session_token",
          "C:/Users/benpe/ClashBot/hogeq/data/royaleapi/crawl2/.session_token"]
CUTOFF = int(dt.datetime(2026, 9, 6, tzinfo=dt.timezone.utc).timestamp())  # no hero-IW data anywhere before this
PAGES_PER_PLAYER = 6
RANKED = ("pathoflegend", "ladder", "ranked")  # substring match on lower-cased battle_type
PLAY_FIELDS = ["replay_tag", "play_index", "tick", "seconds", "x_units", "y_units", "tile_x", "tile_y",
               "attr_ability", "attr_card", "attr_s", "attr_t", "attr_i"]
BFIELDS = pipeline.BATTLE_FIELDS + ["hero_side", "hero_deploys", "battle_key"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def blocked(msg):
    (OUT / "BLOCKED.txt").write_text(msg, encoding="utf-8")
    log("BLOCKED:", msg)
    sys.exit(3)


def has_hero(b):
    return HERO in b["team_deck"].split(",") or HERO in b["opponent_deck"].split(",")


def renew(pages):
    try:
        pages.renew()
    except AuthError as e:                      # Cloudflare verification did not clear on its own
        blocked("Cloudflare verification did not clear: %s" % e)


def call(pages, fn, label):
    for att in range(3):
        try:
            return fn()
        except ClearanceExpired:
            log("clearance expired during", label, "- renew", att)
            renew(pages)
    raise ClearanceExpired(label)


def roster(pages, curl):
    p = OUT / "roster.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    decks = set(call(pages, lambda: parse.similar_decks(curl.get(f"/decks/stats/{SEED}/similar"), SEED), "similar"))
    for path in ("/card/ice-wizard-hero", "/decks/popular?inc=ice-wizard-hero"):
        h = call(pages, lambda path=path: curl.get(path), path)
        decks |= {d for d in re.findall(r"/decks/stats/([a-z0-9,\-]+)", h) if HERO in d.split(",")}
    decks = sorted(d for d in decks if HERO in d.split(","))
    log("hero decks", len(decks))
    players, found_on = {}, {}
    for d in decks:
        try:
            rows = call(pages, lambda d=d: parse.rated_players(curl.get(f"/decks/stats/{d}/players/ratings")), d)
        except (AuthError, RateLimited) as e:
            log("ratings failed", d, type(e).__name__)
            continue
        for r in rows:
            if r["player_tag"] not in players:
                players[r["player_tag"]] = r
                found_on[r["player_tag"]] = d
        log("ratings", d, len(rows), "players so far", len(players))
    ros = {"decks": decks, "players": players, "found_on": found_on}
    p.write_text(json.dumps(ros), encoding="utf-8")
    return ros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-deploys", type=int, default=500)
    ap.add_argument("--max-hours", type=float, default=3.0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "payloads").mkdir(exist_ok=True)
    t0 = time.time()
    pages = Pages()
    try:
        curl = None
        for tp in TOKENS:
            if Path(tp).exists():
                c = Curl(pages, Session("saved", Path(tp).read_text(encoding="utf-8").strip()))
                try:
                    if call(pages, c.logged_in, "login-check"):
                        curl = c
                        log("session accepted (token file not copied)")
                        break
                except Exception as e:
                    log("token rejected", type(e).__name__)
        if curl is None:
            blocked("no saved RoyaleAPI session is accepted; replays are login-gated (needs the owner to log in)")
        ros = roster(pages, curl)
        players = ros["players"]
        log("roster", len(players), "players")
        pd_p, rd_p = OUT / "players_done.json", OUT / "replays_done.json"
        done_pl = set(json.loads(pd_p.read_text())) if pd_p.exists() else set()
        done_rp = set(json.loads(rd_p.read_text())) if rd_p.exists() else set()
        bpath, ppath = OUT / "battles.csv", OUT / "plays.csv"
        seen_key, deploys = set(), 0
        if bpath.exists():
            for r in csv.DictReader(open(bpath, encoding="utf-8")):
                seen_key.add(r["battle_key"]); deploys += int(r["hero_deploys"] or 0)
        new = not bpath.exists()
        bf, pf = bpath.open("a", newline="", encoding="utf-8"), ppath.open("a", newline="", encoding="utf-8")
        bw = csv.DictWriter(bf, BFIELDS)
        pw = csv.DictWriter(pf, PLAY_FIELDS, extrasaction="ignore")
        if new:
            bw.writeheader(); pw.writeheader()
        nbat, refused, types = len(seen_key), 0, {}
        order = sorted(players, key=lambda t: -int(players[t].get("rating") or 0))
        for i, tag in enumerate(order):
            if tag in done_pl:
                continue
            if time.time() - t0 > a.max_hours * 3600 or deploys >= a.target_deploys:
                log("stop: elapsed %.1f h, deploys %d" % ((time.time() - t0) / 3600, deploys))
                break
            rows, path = [], f"/player/{tag}/battles/history"
            try:
                for pg in range(PAGES_PER_PLAYER):
                    html = call(pages, lambda path=path: curl.get(path), "history")
                    fresh = parse.battles(html)
                    rows += fresh
                    nxt = parse.next_history_page(html)
                    oldest = min([b["battle_timestamp"] for b in fresh] or [0])
                    if not fresh or not nxt or oldest < CUTOFF:
                        break
                    path = nxt
            except (AuthError, RateLimited) as e:
                log("history failed", tag, type(e).__name__, str(e)[:80]); continue
            for b in rows:
                types[b["battle_type"]] = types.get(b["battle_type"], 0) + 1
            kept = [b for b in rows if has_hero(b) and b["battle_timestamp"] >= CUTOFF
                    and any(k in b["battle_type"].lower() for k in RANKED)]
            log("player %d/%d %s: %d battles, %d hero-IW kept" % (i + 1, len(order), tag, len(rows), len(kept)))
            for b in kept:
                key = ",".join(sorted(b["team_tags"].split(",") + b["opponent_tags"].split(","))) + "@" + str(b["battle_timestamp"] // 5)
                if b["replay_tag"] in done_rp or key in seen_key:
                    continue
                try:
                    data = call(pages, lambda b=b: curl.json("/data/replay", pipeline.replay_params(b)), "replay")
                    if not data.get("success"):
                        refused += 1
                        log("refused", b["replay_tag"])
                        if refused >= 5:
                            blocked("5 replays refused: login/session expired")
                        continue
                    stats, plays = parse_replay_ext(data["html"])
                except (AuthError, RateLimited, ValueError) as e:
                    log("replay error", b["replay_tag"], type(e).__name__, str(e)[:80]); continue
                refused = 0
                hs = [s for s, d in (("blue", b["team_deck"]), ("red", b["opponent_deck"])) if HERO in d.split(",")]
                n_dep = sum(1 for p in plays if p.get("attr_card") == "ice-wizard" and p.get("attr_s") in hs)
                bw.writerow({**{k: b.get(k, "") for k in pipeline.BATTLE_FIELDS}, **stats, "plays": len(plays),
                             "hero_side": "+".join(hs), "hero_deploys": n_dep, "battle_key": key})
                for p in plays:
                    pw.writerow({k: p.get(k, "") for k in PLAY_FIELDS})
                with gzip.open(OUT / "payloads" / (b["replay_tag"] + ".html.gz"), "wt", encoding="utf-8") as f:
                    f.write(data["html"])
                seen_key.add(key); done_rp.add(b["replay_tag"]); nbat += 1; deploys += n_dep
                bf.flush(); pf.flush()
                log("  replay %s hero_side=%s deploys+%d -> battles %d deploys %d (%.0f min, limiter %s)" % (
                    b["replay_tag"], hs, n_dep, nbat, deploys, (time.time() - t0) / 60, curl.limiter))
            done_pl.add(tag)
            pd_p.write_text(json.dumps(sorted(done_pl)), encoding="utf-8")
            rd_p.write_text(json.dumps(sorted(done_rp)), encoding="utf-8")
        (OUT / "battle_types_seen.json").write_text(json.dumps(types), encoding="utf-8")
        log("DONE battles %d deploys %d in %.1f min" % (nbat, deploys, (time.time() - t0) / 60))
    finally:
        pages.close()


if __name__ == "__main__":
    main()
