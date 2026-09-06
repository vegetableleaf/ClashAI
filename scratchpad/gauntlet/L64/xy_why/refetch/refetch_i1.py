"""Re-fetch the 'uncovered' replays (x/y fraction < 0.5 in plays_ext.csv) with a marker join that
does not key on data-i (which is a per-replay flag, not an occurrence index -- L64/xy_why).
Writes ONLY new files: <OUT>/payloads/<tag>.html (raw payload kept this time) and
<OUT>/plays_ext_i1.csv (+ attr_i column, coordinates exactly as the payload gives them, no
frame transform). Progress in <here>/<deck>_done.json. No interactive login: exits NO_SESSION.
usage: refetch_i1.py --deck icebow|hogeq [--limit N]"""
import sys, csv, json, time, argparse, collections
from pathlib import Path
sys.path.insert(0, "C:/Users/benpe/clash-replay-scraper")
from royale.cookies import Session, find_sessions
from royale.transport import AuthError, ClearanceExpired, Curl, Pages, RateLimited
from royale import pipeline
from bs4 import BeautifulSoup
import crawl_icebow as ci                       # _stage, parse (main is guarded)

HERE = Path(__file__).resolve().parent
OUTS = {"icebow": Path("C:/Users/benpe/ClashBot/icebow/data/royaleapi/crawl2"),
        "hogeq": Path("C:/Users/benpe/ClashBot/hogeq/data/royaleapi/crawl2")}
SIDE = {"t": "blue", "o": "red"}


def parse_replay_i1(html):
    d = BeautifulSoup(html, "lxml")
    root = d.select_one(".battle_replay")
    tag = root.get("data-tag", "") if root else ""
    markers = collections.defaultdict(list)
    for m in d.select(".marker"):
        if not m.get("data-t"):
            continue
        markers[(m.get("data-t", ""), m.get("data-c", ""), SIDE.get(m.get("data-s", ""), ""))].append(
            (m.get("data-x", ""), m.get("data-y", ""), m.get("data-i", "")))
    cards = sorted(d.select(".replay_timeline .replay_card"), key=lambda c: int(c.get("data-t", 0)))
    plays = []
    for i, c in enumerate(cards):
        row = {("attr_" + k[5:]): v for k, v in c.attrs.items() if k.startswith("data-")}
        lst = markers.get((c.get("data-t", ""), c.get("data-card", ""), c.get("data-s", "")))
        if lst:
            mx = lst.pop(0)
            row["x_units"], row["y_units"], row["attr_i"] = mx[0], mx[1], mx[2]
            try:
                row["tile_x"] = round(int(mx[0]) / 1000.0, 2)
                row["tile_y"] = round(int(mx[1]) / 1000.0, 2)
            except ValueError:
                pass
        row.update({"replay_tag": tag, "play_index": i, "tick": int(c.get("data-t", 0)),
                    "seconds": round(int(c.get("data-t", 0)) / ci.parse.TPS, 2)})
        plays.append(row)
    return plays


def uncovered_tags(out):
    n = collections.Counter(); k = collections.Counter()
    for r in csv.DictReader(open(out / "plays_ext.csv", encoding="utf-8")):
        if r.get("attr_ability") == "1":
            continue
        n[r["replay_tag"]] += 1
        k[r["replay_tag"]] += bool(r.get("x_units"))
    return [t for t in n if k[t] / n[t] < 0.5]


def connect():
    pages = Pages(); curl = None
    for cand in find_sessions():
        c = Curl(pages, cand)
        try:
            if c.logged_in():
                curl = c; print("[refetch] session: jar", flush=True); break
        except (ClearanceExpired, AuthError) as e:
            print("[refetch] jar session %s: %s" % (cand, type(e).__name__), flush=True)
            try:
                pages.renew()
            except AuthError:
                pass
    tok = OUTS["icebow"] / ".session_token"
    if curl is None and tok.exists():
        c = Curl(pages, Session("saved", tok.read_text(encoding="utf-8").strip()))
        for att in range(3):
            try:
                if c.logged_in():
                    curl = c; print("[refetch] session: saved token", flush=True)
                break
            except (ClearanceExpired, AuthError) as e:
                print("[refetch] saved token attempt %d: %s" % (att, type(e).__name__), flush=True)
                try:
                    pages.renew()
                except AuthError:
                    pass
    return pages, curl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", required=True, choices=list(OUTS))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    out = OUTS[a.deck]
    done_p = HERE / f"{a.deck}_done.json"
    done = set(json.loads(done_p.read_text())) if done_p.exists() else set()
    rows = {r["replay_tag"]: r for r in csv.DictReader(open(out / "battles.csv", encoding="utf-8"))}
    todo = [t for t in uncovered_tags(out) if t not in done and t in rows]
    if a.limit:
        todo = todo[:a.limit]
    print("[refetch] %s: %d uncovered to fetch (%d done)" % (a.deck, len(todo), len(done)), flush=True)
    pages, curl = connect()
    if curl is None:
        print("NO_SESSION", flush=True); pages.close(); sys.exit(2)
    (out / "payloads").mkdir(exist_ok=True)
    ppath = out / "plays_ext_i1.csv"
    new = not ppath.exists()
    pf = ppath.open("a", newline="", encoding="utf-8")
    fields = ["replay_tag", "play_index", "tick", "seconds", "x_units", "y_units", "tile_x", "tile_y",
              "attr_ability", "attr_card", "attr_s", "attr_t", "attr_i"]
    pw = csv.DictWriter(pf, fields, extrasaction="ignore")
    if new:
        pw.writeheader()
    t0 = time.time(); n = 0; errs = collections.Counter(); ivals = collections.Counter()
    try:
        for tag in todo:
            b = rows[tag]
            try:
                data = ci._stage(pages, lambda b=b: curl.json("/data/replay", pipeline.replay_params(b)), "replay")
                if not data.get("success"):
                    print("[refetch] refused %s" % tag, flush=True); errs["refused"] += 1; continue
                (out / "payloads" / f"{tag}.html").write_text(data["html"], encoding="utf-8")
                plays = parse_replay_i1(data["html"])
            except RateLimited as e:
                print("[refetch] ratelimited %s -- sleeping 120 s" % tag, flush=True); errs["RateLimited"] += 1
                time.sleep(120); continue
            except Exception as e:                       # noqa: BLE001
                print("[refetch] error %s: %s" % (tag, type(e).__name__), flush=True); errs[type(e).__name__] += 1
                continue
            for p in plays:
                pw.writerow({k: p.get(k, "") for k in fields})
            ivals.update(p.get("attr_i", "") for p in plays if p.get("x_units"))
            done.add(tag); n += 1
            if n % 10 == 0:
                pf.flush(); done_p.write_text(json.dumps(sorted(done)))
                print("[refetch] %d/%d (%.0f min) i-values %s errs %s" % (
                    n, len(todo), (time.time() - t0) / 60, dict(ivals), dict(errs)), flush=True)
    finally:
        pf.close(); done_p.write_text(json.dumps(sorted(done))); pages.close()
    print("[refetch] DONE %s: %d fetched in %.0f min; i-values %s; errs %s" % (
        a.deck, n, (time.time() - t0) / 60, dict(ivals), dict(errs)), flush=True)


if __name__ == "__main__":
    main()
