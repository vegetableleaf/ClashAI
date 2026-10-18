"""Successor loss review (10-17 night): append Mark CXXXVIII (cue130, live since 13:29) + Mark CXXIV (u250) logs to the
standing loss-review ledger in review.py's own format (analyzed.txt + matches.jsonl), and write per-match EXTRAS the review
rows do not keep (opponent tower max_hp / reader levels, opponent card levels) to extras.jsonl here.

  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/successor/loss_review/ingest.py [--dry]

Only these two checkpoints' logs are parsed (the other unanalysed logs stay for review.py's next run: it skips by membership).
Below-normal priority, single process, read-only on the live logs.
"""
import ctypes, glob, json, os, sys, time
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
LR = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/loss_review/"
sys.path.insert(0, LR)
import review as V

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
EXTRAS = HERE + "extras.jsonl"
CKPTS = {"rlarm_gae_cue_u250_u0130_grafted.pt": "CXXXVIII", "rlarm_gae_u0250_grafted.pt": "CXXIV"}


def head_ckpt(f):
    try: h = json.loads(open(f, encoding="utf8", errors="replace").readline())
    except ValueError: return None
    return os.path.basename(str(h.get("ckpt") or "").replace("\\", "/"))


def extras(f):
    """opponent tower max_hp + reader level per tower, opponent card levels (frame ents_state[2]) per first-seen entity."""
    tw, lv, side, seen = {}, {}, None, set()
    with open(f, encoding="utf8", errors="replace") as fh:
        for i, l in enumerate(fh):
            if l.startswith('{"event": "frame"') and '"ents_state"' in l:
                if i % 4: continue                                    # every 4th line is plenty for first sightings
                try: d = json.loads(l)
                except ValueError: continue
                side = d.get("my_side", side)
                for e, st in zip(d.get("ents") or [], d.get("ents_state") or []):
                    if e[0] == side or len(st) < 3: continue
                    cid, addr = e[3], (e[7] if len(e) > 7 else None)
                    if cid == -1:
                        tw.setdefault(f"{e[1]}_{e[2]}", (e[5], st[2]))
                    elif addr not in seen:
                        seen.add(addr); lv.setdefault(str(cid), []).append(st[2])
            elif not tw and l.startswith('{"event": "decision"'):
                try: p = json.loads(l)["public"]
                except (ValueError, KeyError): continue
                me = p.get("observer_side")
                for b in p.get("raw_bodies", []):
                    if b["card_id"] == -1 and b["side"] != me: tw.setdefault(f"{b['x']}_{b['y']}", (b["max_hp"], None))
    return dict(opp_towers=sorted(tw.values(), key=lambda x: -(x[0] or 0)), opp_card_levels=lv)


def main(dry=False):
    names, costs, uv = V._catalog(); V.NAME.update(names); V.NCOST.update(costs); V.UV.update(uv)
    done = set(l.strip() for l in open(V.LEDGER)) - {""}
    have_x = set()
    if os.path.exists(EXTRAS): have_x = {json.loads(l)["file"] for l in open(EXTRAS)}
    now = time.time(); todo = []
    for f in sorted(glob.glob(V.LOGDIR + "live_play_2026101*.jsonl")):
        if now - os.path.getmtime(f) < V.MIN_AGE_S: continue
        ck = head_ckpt(f)
        if ck in CKPTS: todo.append((f, CKPTS[ck]))
    print(len(todo), "logs of the two Marks;", sum(os.path.basename(f) not in done for f, _ in todo), "not in the ledger", flush=True)
    if dry: return
    t0 = time.time()
    for i, (f, mark) in enumerate(todo):
        b = os.path.basename(f)
        if b not in done:
            r = V.parse(f)
            if not (r["end"] or r["stop"]) and now - os.path.getmtime(f) < 86400: continue
            try: row = V.features(r)
            except Exception as e: row = dict(file=r["file"], ts=r["file"][10:25], error=f"{type(e).__name__}: {e}", valid_state=False)
            with open(V.ROWS, "a") as fh: fh.write(json.dumps(row, default=str) + "\n")
            with open(V.LEDGER, "a") as fh: fh.write(r["file"] + "\n")
        if b not in have_x:
            x = extras(f); x.update(file=b, mark=mark)
            with open(EXTRAS, "a") as fh: fh.write(json.dumps(x) + "\n")
        if i % 25 == 0: print(f"[{i}/{len(todo)}] {b} {time.time() - t0:.0f}s", flush=True)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main("--dry" in sys.argv)
