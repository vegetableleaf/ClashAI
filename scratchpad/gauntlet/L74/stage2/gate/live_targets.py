"""Stage-2 GATE, live side: the targets a SIM opponent set must reproduce, with Wilson CIs and n.
Read-only. Results = monitor/card_use.results (ladder line, else the trophy-total inference for missed result screens),
fallback = the log's crown-derived result. Start trophies = the last '[ladder] trophies: N total' read rolled forward by deltas.
Rows = the loss-review ledger (L74/loss_review/matches.jsonl); logs of the two Marks newer than the ledger are parsed in memory
(review.parse/features), nothing is appended anywhere. Archetype = live_eval.classify on PLAYED opponent cards.
  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/stage2/gate/live_targets.py  -> live_targets.json + stdout
"""
import ctypes, glob, json, os, re, sys, collections
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
ROOT = "C:/Users/benpe/ClashBot/"
LR = ROOT + "scratchpad/gauntlet/L74/loss_review/"
sys.path[:0] = [LR, ROOT, ROOT + "scratchpad/gauntlet/L74/monitor/"]
import review as V
import report as R
import card_use as CU
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
MARKS = {"rlarm_gae_cue_u250_u0130_grafted.pt": "CXXXVIII", "rlarm_gae_u0250_grafted.pt": "CXXIV"}
REG_END = 3600


def starts():
    """log -> trophies at match start (anchor reads rolled forward by logged deltas)."""
    out, est, last = {}, None, None
    for line in open(V.OVN, encoding="utf8", errors="replace"):
        m = re.match(r"\[ladder\] trophies: (\d+) total", line)
        if m: est = int(m[1]); continue
        if line.startswith("{") and '"log"' in line:
            try: last = os.path.basename(json.loads(line)["log"].replace("\\", "/")); out[last] = est
            except (ValueError, KeyError): last = None
            continue
        m = re.match(r"\[ladder\] result: (\w+).*?trophies ([+-]?\d+)", line)
        if m and last and est is not None: est += int(m[2]); last = None
    return out


def head_ckpt(f):
    try: return os.path.basename(str(json.loads(open(f, encoding="utf8", errors="replace").readline()).get("ckpt") or "").replace("\\", "/"))
    except ValueError: return None


def wil(k, n):
    if not n: return "n/a"
    lo, hi = V.wilson(k, n); return f"{k}/{n} = {k / n:.1%} [{lo:.1%}, {hi:.1%}]"


def main():
    names, costs, uv = V._catalog(); V.NAME.update(names); V.NCOST.update(costs); V.UV.update(uv)
    res, st = CU.results(), starts()
    rows = {}
    for l in open(V.ROWS):
        if '"file": "live_play_2026' not in l[:60]: continue
        r = json.loads(l); rows[r["file"]] = r
    for f in sorted(glob.glob(V.LOGDIR + "live_play_202610*.jsonl")):     # the two Marks' logs newer than the ledger
        b = os.path.basename(f)
        if b in rows or head_ckpt(f) not in MARKS: continue
        r = V.parse(f)
        if not (r["end"] or r["stop"]): continue
        try: rows[b] = V.features(r)
        except Exception: pass
    out = []
    for b, r in rows.items():
        if r.get("dry_run") or (r.get("n_plays") or 0) < 5 or not r.get("valid_state"): continue
        lr = res.get(b)
        result = lr[0] if lr else r.get("derived")
        if result not in ("WIN", "LOSS", "DRAW"): continue
        out.append(dict(file=b, ts=b[10:25], ck=os.path.basename(str(r.get("ckpt") or "")), mark=MARKS.get(os.path.basename(str(r.get("ckpt") or ""))),
                        res=result, src="ladder" if lr else "derived", start=st.get(b), ot=(r.get("dur_s") or 0) >= 186, dur_s=r.get("dur_s"),
                        end_tick=r.get("end_tick"), cls=R.classify(r.get("opp_cards") or []), opp_cards=r.get("opp_cards")))
    json.dump(out, open(HERE + "live_targets.json", "w"))
    W = lambda Q: sum(x["res"] == "WIN" for x in Q)
    for mk in ("CXXXVIII", "CXXIV"):
        Q = [x for x in out if x["mark"] == mk and x["src"] == "ladder"]
        Qa = [x for x in out if x["mark"] == mk]
        print(f"\n== {mk}: ladder-graded {wil(W(Q), len(Q))}; incl. crown-derived {wil(W(Qa), len(Qa))}; "
              f"{min(x['ts'] for x in Qa)}..{max(x['ts'] for x in Qa)}")
        bands = (("<12500", lambda s: s < 12500), ("12500-12999", lambda s: 12500 <= s < 13000), (">=13000", lambda s: s >= 13000))
        for bn, bf in bands:
            B = [x for x in Q if x["start"] is not None and bf(x["start"])]
            if not B: continue
            O = [x for x in B if x["ot"]]
            print(f"   band {bn:12s} all {wil(W(B), len(B)):34s} OT {wil(W(O), len(O)):30s} OT share {len(O) / len(B):.0%}")
        O = [x for x in Q if x["ot"]]
        print(f"   OT all bands {wil(W(O), len(O))}")
        c = collections.Counter(x["cls"] for x in Q)
        for k, n in c.most_common():
            K = [x for x in Q if x["cls"] == k]; H = [x for x in K if x["start"] is not None and x["start"] >= 13000]
            print(f"   {k:30s} {wil(W(K), n):34s} at 13k+ {wil(W(H), len(H))}")
    # all icebow main-account history (any Mark) by trophy band: is the 13k OT collapse a band effect or a CXXXVIII effect?
    Q = [x for x in out if x["src"] == "ladder" and x["start"] and "bait" not in x["ck"].lower()]
    print("\n== all icebow-ladder matches with a trophy start, OT by band (any model)")
    for lo in range(9000, 13500, 500):
        B = [x for x in Q if lo <= x["start"] < lo + 500]
        if len(B) < 10: continue
        O = [x for x in B if x["ot"]]; ms = collections.Counter(x["mark"] or "other" for x in B)
        print(f"   {lo}-{lo + 499}: all {wil(W(B), len(B)):34s} OT {wil(W(O), len(O)):30s} models {dict(ms)}")


if __name__ == "__main__":
    main()
