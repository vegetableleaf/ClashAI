"""Cheap-card spam audit (owner 10-14 evening): per live match since A/B1, plays/min of Skeletons + Log, same-card repeats
within 6 s, elixir at cheap plays; grouped by model / A/B arm / hour."""
import collections, glob, json, os, statistics as st

LOG = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
AB = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/ab/results.jsonl"
arm = {}
for l in open(AB, encoding="utf8"):
    r = json.loads(l)
    arm[os.path.basename(r["match_file"])] = (r["run_id"][:13], r["arm"])
CHEAP = {"Skeletons", "Log", "TheLog", "The Log"}
rows = []
for f in sorted(glob.glob(LOG + "live_play_2026101[34]_*.jsonl")):
    b = os.path.basename(f)
    if b < "live_play_20261013_0948":
        continue
    head, plays, end = None, [], None
    with open(f, encoding="utf8", errors="replace") as fh:
        for l in fh:
            if head is None:
                head = json.loads(l)
                continue
            if l.startswith('{"event": "play"'):
                j = json.loads(l)
                plays.append((j["tick"], j["name"], j.get("elixir")))
            elif l.startswith('{"event": "end"') or l.startswith('{"event": "stop"'):
                pass
            elif '"tick"' in l[:40]:
                try:
                    end = max(end or 0, json.loads(l).get("tick") or 0)
                except ValueError:
                    pass
    if head is None or head.get("dry_run") or not plays:
        continue
    mins = max(1.0, (end or plays[-1][0]) / 1200.0)
    cheap = [p for p in plays if p[1] in CHEAP]
    rep = sum(1 for a, c in zip(plays, plays[1:]) if a[1] == c[1] and a[1] in CHEAP and c[0] - a[0] <= 120)
    opts = (head.get("live_options") or {}).get("from_file") or {}
    sha = (head.get("ckpt_sha256") or "")[:8]
    run, a = arm.get(b, ("-", "-"))
    rows.append(dict(f=b, hour=b[10:21], sha=sha, run=run, arm=a, iw=opts.get("iw_press", "rule"), emo=head.get("emote_spam", "off"),
                     mins=mins, plays=len(plays), cheap=len(cheap), rep=rep,
                     el=[p[2] for p in cheap if p[2] is not None], skel=sum(p[1] == "Skeletons" for p in plays)))


def show(name, rs):
    if not rs:
        return
    m = sum(r["mins"] for r in rs)
    el = [e for r in rs for e in r["el"]]
    print(f"{name:42s} n={len(rs):3d} plays/min {sum(r['plays'] for r in rs)/m:5.2f}  cheap/min {sum(r['cheap'] for r in rs)/m:4.2f}  "
          f"skel/min {sum(r['skel'] for r in rs)/m:4.2f}  repeats/match {sum(r['rep'] for r in rs)/len(rs):4.2f}  "
          f"elixir@cheap {st.median(el) if el else float('nan'):4.1f}")


G = collections.defaultdict(list)
for r in rows:
    if r["run"].startswith("20261013_0948"):
        G[f"A/B1 {r['arm']} ({r['sha']})"].append(r)
    elif r["run"].startswith("20261014_1259"):
        G[f"A/B2 {r['arm']} ({r['sha']})"].append(r)
    elif r["run"].startswith("20261014_1343"):
        G[f"A/B3 {r['arm']} iw={r['iw']} {'<19:00' if r['hour'] < '20261014_19' else '>=19:00'}"].append(r)
    else:
        G[f"other {r['sha']} {r['hour'][:8]}"].append(r)
for k in sorted(G):
    show(k, G[k])
print()
for r in rows[-12:]:
    print(r["f"], r["arm"], r["iw"], f"cheap {r['cheap']} rep {r['rep']} plays {r['plays']} min {r['mins']:.1f}")
