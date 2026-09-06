"""Sharded re-fetch: one process per RoyaleAPI account, disjoint tag slices, separate output files.

Each process gets its OWN session token (--token), its own Limiter (inside its own Curl) and its own
browser for the Cloudflare clearance, so N processes push ~N x the request rate at the site. Whether
that actually buys throughput is the open question: if the 429 counter is keyed on the account, yes;
if it is keyed on the IP (one machine, one address, and cf_clearance is IP-pinned), no. `--shard`
plus the per-shard output files is what makes the comparison measurable and the runs resumable.

Never commit a token file and never print a token.

usage: refetch_par.py --deck icebow --shard 0/2 --token <path to .session_token_1>
       merge with: refetch_par.py --deck icebow --merge
"""
import sys, csv, json, time, argparse, collections, zlib
from pathlib import Path

sys.path.insert(0, "C:/Users/benpe/clash-replay-scraper")
from royale.cookies import Session
from royale.transport import AuthError, ClearanceExpired, Curl, Pages, RateLimited
from royale import pipeline
import crawl_icebow as ci

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from refetch_i1 import OUTS, parse_replay_i1, uncovered_tags

FIELDS = ["replay_tag", "play_index", "tick", "seconds", "x_units", "y_units", "tile_x", "tile_y",
          "attr_ability", "attr_card", "attr_s", "attr_t", "attr_i"]


def connect(token_path):
    """One browser + one Curl bound to the token in `token_path`. No browser-jar fallback:
    a shard must use the account it was given, or none."""
    pages = Pages()
    tok = Path(token_path).read_text(encoding="utf-8").strip()
    c = Curl(pages, Session("file:" + Path(token_path).name, tok))
    for att in range(3):
        try:
            if c.logged_in():
                return pages, c
            break
        except (ClearanceExpired, AuthError) as e:
            print("[shard] token attempt %d: %s" % (att, type(e).__name__), flush=True)
            try:
                pages.renew()
            except AuthError:
                pass
    pages.close()
    return None, None


def merge(deck):
    """Union the shard outputs into the canonical plays_ext_i1.csv / <deck>_done.json."""
    out = OUTS[deck]
    done_p = HERE / f"{deck}_done.json"
    done = set(json.loads(done_p.read_text())) if done_p.exists() else set()
    seen_rows = 0
    ppath = out / "plays_ext_i1.csv"
    new = not ppath.exists()
    with ppath.open("a", newline="", encoding="utf-8") as pf:
        pw = csv.DictWriter(pf, FIELDS, extrasaction="ignore")
        if new:
            pw.writeheader()
        for sh in sorted(out.glob(f"plays_ext_i1_sh*.csv")):
            for r in csv.DictReader(open(sh, encoding="utf-8")):
                if r["replay_tag"] in done:      # already merged on an earlier pass
                    continue
                pw.writerow(r); seen_rows += 1
        for dp in sorted(HERE.glob(f"{deck}_done_sh*.json")):
            done |= set(json.loads(dp.read_text()))
    done_p.write_text(json.dumps(sorted(done)))
    print("[merge] %s: +%d rows, done now %d" % (deck, seen_rows, len(done)), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", required=True, choices=list(OUTS))
    ap.add_argument("--shard", default="0/1", help="i/n -- this process takes tags with crc32(tag)%%n == i")
    ap.add_argument("--token", help="file holding this shard's __royaleapi_session_v2 value")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--merge", action="store_true")
    # Backoff: the old loop slept a flat 120 s on a 429 AND dropped the tag -- 63% of three runs'
    # wall clock went into those sleeps (L64n). The transport's AIMD limiter already halves the
    # rate on every 429, so the extra sleep only has to let the server's window roll over.
    ap.add_argument("--rl-sleep", type=float, default=15.0, help="pause after a 429 (was a fixed 120)")
    ap.add_argument("--rl-passes", type=int, default=2, help="re-queue rate-limited tags this many times")
    ap.add_argument("--stats", help="write a JSON line of throughput stats here")
    a = ap.parse_args()
    if a.merge:
        merge(a.deck); return
    if not a.token:
        print("NO_TOKEN -- pass --token <file>", flush=True); sys.exit(2)
    i, n = (int(x) for x in a.shard.split("/"))
    out = OUTS[a.deck]

    # Every shard's own done-set, plus the canonical one, so a merged tag is never re-fetched.
    done_p = HERE / f"{a.deck}_done_sh{i}.json"
    done = set(json.loads(done_p.read_text())) if done_p.exists() else set()
    canon = HERE / f"{a.deck}_done.json"
    if canon.exists():
        done |= set(json.loads(canon.read_text()))
    rows = {r["replay_tag"]: r for r in csv.DictReader(open(out / "battles.csv", encoding="utf-8"))}
    todo = [t for t in uncovered_tags(out)
            if t not in done and t in rows and zlib.crc32(t.encode()) % n == i]
    if a.limit:
        todo = todo[:a.limit]
    print("[shard %d/%d] %s: %d to fetch (%d already done)" % (i, n, a.deck, len(todo), len(done)), flush=True)

    pages, curl = connect(a.token)
    if curl is None:
        print("NO_SESSION", flush=True); sys.exit(2)
    (out / "payloads").mkdir(exist_ok=True)
    ppath = out / f"plays_ext_i1_sh{i}.csv"
    new = not ppath.exists()
    pf = ppath.open("a", newline="", encoding="utf-8")
    pw = csv.DictWriter(pf, FIELDS, extrasaction="ignore")
    if new:
        pw.writeheader()
    t0 = time.time(); nf = 0; errs = collections.Counter(); ivals = collections.Counter()
    slept = 0.0; queue = list(todo); retry = []; passes = 0
    try:
        while queue:
          for tag in queue:
              b = rows[tag]
              try:
                  data = ci._stage(pages, lambda b=b: curl.json("/data/replay", pipeline.replay_params(b)), "replay")
                  if not data.get("success"):
                      print("[shard %d] refused %s" % (i, tag), flush=True); errs["refused"] += 1; continue
                  (out / "payloads" / f"{tag}.html").write_text(data["html"], encoding="utf-8")
                  plays = parse_replay_i1(data["html"])
              except RateLimited:
                  errs["RateLimited"] += 1
                  if passes < a.rl_passes:
                      retry.append(tag)                 # not lost: taken again on the next pass
                  print("[shard %d] ratelimited %s -- %.0f s, %s" % (i, tag, a.rl_sleep, curl.limiter), flush=True)
                  time.sleep(a.rl_sleep); slept += a.rl_sleep; continue
              except Exception as e:                       # noqa: BLE001
                  print("[shard %d] error %s: %s" % (i, tag, type(e).__name__), flush=True)
                  errs[type(e).__name__] += 1; continue
              for p in plays:
                  pw.writerow({k: p.get(k, "") for k in FIELDS})
              ivals.update(p.get("attr_i", "") for p in plays if p.get("x_units"))
              done.add(tag); nf += 1
              if nf % 10 == 0:
                  pf.flush(); done_p.write_text(json.dumps(sorted(done)))
                  print("[shard %d] %d/%d (%.0f min) rate %s i %s errs %s" % (
                      i, nf, len(todo), (time.time() - t0) / 60, curl.limiter, dict(ivals), dict(errs)), flush=True)
          # end of this pass: whatever got 429'd goes round again, once the limiter has recovered
          queue, retry, passes = retry, [], passes + 1
          if queue:
              print("[shard %d] pass %d: %d re-queued" % (i, passes, len(queue)), flush=True)
    finally:
        pf.close(); done_p.write_text(json.dumps(sorted(done))); pages.close()
    wall = time.time() - t0
    st = {"shard": i, "n": n, "deck": a.deck, "fetched": nf, "wall_s": round(wall, 1),
          "slept_s": round(slept, 1), "sleep_frac": round(slept / wall, 3) if wall else 0,
          "s_per_replay": round((wall - slept) / nf, 2) if nf else None,
          "s_per_replay_wall": round(wall / nf, 2) if nf else None,
          "rate_now": round(curl.limiter.rate, 2), "rate_peak": round(curl.limiter.peak, 2),
          "n_429": curl.limiter.hits, "requests": curl.limiter.sent, "errs": dict(errs)}
    print("[shard %d] DONE %s" % (i, json.dumps(st)), flush=True)
    if a.stats:
        with open(a.stats, "a", encoding="utf-8") as f:
            f.write(json.dumps(st) + chr(10))


if __name__ == "__main__":
    main()
