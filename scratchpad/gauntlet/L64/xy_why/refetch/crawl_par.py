"""Sharded replay-fetch for NEW battles -- crawl_icebow.py's stage 2, one process per account.

Same parser and the same output columns as the crawler (`parse_replay_ext`, `pipeline.BATTLE_FIELDS`),
so shard output merges straight into battles.csv / plays_ext.csv. What is different:
  * `--token` pins the account, `--shard i/n` splits the backlog by crc32(tag) -- disjoint, resumable;
  * a 429 re-queues the tag (`--rl-passes`) after a short `--rl-sleep` instead of dropping it after a
    flat 120 s: three earlier runs spent 62-63% of their wall clock in that sleep (L64n);
  * `--stats` writes one JSON line of throughput so the 1-account and 3-account arms are comparable.

The experiment this exists for: is RoyaleAPI's 429 counted per ACCOUNT or per IP? Same code, same box,
same backlog, N=1 then N=3. Per-account => ~3x the replays/min; per-IP => the same total and 3x the 429s.

Never commit a token file and never print a token.

usage: crawl_par.py --shard 0/3 --token <file> --limit 60 --stats runs.jsonl
       crawl_par.py --merge
"""
import sys, csv, json, time, argparse, collections, zlib
from pathlib import Path

sys.path.insert(0, "C:/Users/benpe/clash-replay-scraper")
from royale.transport import RateLimited
from royale import pipeline
import crawl_icebow as ci
from crawl_icebow import parse_replay_ext

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from refetch_par import connect

OUT = Path("C:/Users/benpe/ClashBot/icebow/data/royaleapi/crawl2")
PLAY_FIELDS = ["replay_tag", "play_index", "tick", "seconds", "x_units", "y_units", "tile_x", "tile_y",
               "attr_ability", "attr_card", "attr_i", "attr_s", "attr_t"]


def backlog():
    """Battles discovered but not yet fetched, in the crawler's own order (wins first, then rating)."""
    rows = json.loads((OUT / "battles_raw.json").read_text(encoding="utf-8"))
    done_p = OUT / "replays_done.json"
    done = set(json.loads(done_p.read_text(encoding="utf-8"))) if done_p.exists() else set()
    todo = [b for b in rows if b["replay_tag"] not in done]
    todo.sort(key=lambda b: (b.get("result") != "win", -int(b.get("rating") or 0)))
    return todo, done


def merge():
    """Fold every shard's rows into battles.csv / plays_ext.csv and mark them done."""
    done_p = OUT / "replays_done.json"
    done = set(json.loads(done_p.read_text(encoding="utf-8"))) if done_p.exists() else set()
    bpath, ppath = OUT / "battles.csv", OUT / "plays_ext.csv"
    nb = np = 0
    with bpath.open("a", newline="", encoding="utf-8") as bf, ppath.open("a", newline="", encoding="utf-8") as pf:
        bw = csv.DictWriter(bf, pipeline.BATTLE_FIELDS + ["plays"], extrasaction="ignore")
        pw = csv.DictWriter(pf, PLAY_FIELDS, extrasaction="ignore")
        added = set()
        for sh in sorted(OUT.glob("battles_sh*.csv")):
            for r in csv.DictReader(open(sh, encoding="utf-8")):
                if r["replay_tag"] in done:
                    continue
                bw.writerow(r); added.add(r["replay_tag"]); nb += 1
        for sh in sorted(OUT.glob("plays_ext_sh*.csv")):
            for r in csv.DictReader(open(sh, encoding="utf-8")):
                if r["replay_tag"] in added:
                    pw.writerow(r); np += 1
    done |= added
    done_p.write_text(json.dumps(sorted(done)), encoding="utf-8")
    print("[merge] +%d battles, +%d play rows; replays_done now %d" % (nb, np, len(done)), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--token")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rl-sleep", type=float, default=15.0)
    ap.add_argument("--rl-passes", type=int, default=2)
    ap.add_argument("--stats")
    ap.add_argument("--label", default="")
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    if a.merge:
        merge(); return
    if not a.token:
        print("NO_TOKEN -- pass --token <file>", flush=True); sys.exit(2)
    i, n = (int(x) for x in a.shard.split("/"))

    todo, done = backlog()
    mine = [b for b in todo if zlib.crc32(b["replay_tag"].encode()) % n == i]
    if a.limit:
        mine = mine[:a.limit]
    print("[shard %d/%d] %d to fetch (backlog %d, done %d)" % (i, n, len(mine), len(todo), len(done)), flush=True)

    pages, curl = connect(a.token)
    if curl is None:
        print("NO_SESSION", flush=True); sys.exit(2)
    bpath, ppath = OUT / f"battles_sh{i}.csv", OUT / f"plays_ext_sh{i}.csv"
    newb, newp = not bpath.exists(), not ppath.exists()
    bf = bpath.open("a", newline="", encoding="utf-8")
    pf = ppath.open("a", newline="", encoding="utf-8")
    bw = csv.DictWriter(bf, pipeline.BATTLE_FIELDS + ["plays"], extrasaction="ignore")
    pw = csv.DictWriter(pf, PLAY_FIELDS, extrasaction="ignore")
    if newb:
        bw.writeheader()
    if newp:
        pw.writeheader()

    t0 = time.time(); nf = 0; slept = 0.0; errs = collections.Counter()
    queue = list(mine); retry = []; passes = 0
    try:
        while queue:
            for b in queue:
                tag = b["replay_tag"]
                try:
                    data = ci._stage(pages, lambda b=b: curl.json("/data/replay",
                                                                  pipeline.replay_params(b)), "replay")
                    if not data.get("success"):
                        errs["refused"] += 1; continue
                    stats, plays = parse_replay_ext(data["html"])
                except RateLimited:
                    errs["RateLimited"] += 1
                    if passes < a.rl_passes:
                        retry.append(b)
                    print("[shard %d] 429 %s -- %.0fs, %s" % (i, tag, a.rl_sleep, curl.limiter), flush=True)
                    time.sleep(a.rl_sleep); slept += a.rl_sleep; continue
                except Exception as e:                            # noqa: BLE001
                    errs[type(e).__name__] += 1
                    print("[shard %d] error %s: %s" % (i, tag, type(e).__name__), flush=True); continue
                bw.writerow({**{k: b.get(k, "") for k in pipeline.BATTLE_FIELDS},
                             **stats, "plays": len(plays)})
                for p in plays:
                    pw.writerow({k: p.get(k, "") for k in PLAY_FIELDS})
                nf += 1
                if nf % 10 == 0:
                    bf.flush(); pf.flush()
                    print("[shard %d] %d/%d (%.1f min) %s errs %s" % (
                        i, nf, len(mine), (time.time() - t0) / 60, curl.limiter, dict(errs)), flush=True)
            queue, retry, passes = retry, [], passes + 1
            if queue:
                print("[shard %d] pass %d: %d re-queued" % (i, passes, len(queue)), flush=True)
    finally:
        bf.close(); pf.close(); pages.close()
    wall = time.time() - t0
    st = {"label": a.label, "shard": i, "n": n, "fetched": nf, "wall_s": round(wall, 1),
          "slept_s": round(slept, 1), "s_per_replay_wall": round(wall / nf, 2) if nf else None,
          "replays_per_min": round(nf / (wall / 60), 2) if wall else None,
          "rate_now": round(curl.limiter.rate, 2), "rate_peak": round(curl.limiter.peak, 2),
          "n_429": curl.limiter.hits, "requests": curl.limiter.sent, "errs": dict(errs)}
    print("[shard %d] DONE %s" % (i, json.dumps(st)), flush=True)
    if a.stats:
        with open(a.stats, "a", encoding="utf-8") as f:
            f.write(json.dumps(st) + chr(10))


if __name__ == "__main__":
    main()
