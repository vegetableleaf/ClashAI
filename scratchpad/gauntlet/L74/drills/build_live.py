"""(copied from L74/mistakes/build.py @6455053; output -> drills/data/) L74 mistake catalogue -- step 1: normalise every live log with board state into data/live.pkl.gz.

  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/mistakes/build.py          (single core, below-normal priority)

Per match:  S = [(t, el, hand, eb, tw, dec, own, proj)]  (decision states; frame states for logs without decisions)
  eb   enemy bodies (cls, X, Y, val, addr, t_first, hpf, air)   cls = the class the MODEL receives (pipeline.body_identity
       resolve_board on the raw catalog name + max_hp + form + tower level, as obs_contract fv5 does), val = elixir value of
       that class (unit_values.json per unit; spawned children valued as the child, CHILD below)
  tw   tower hp {mL, mR, mK, eL, eR, eK} (a tower seen then missing = 0); twmax the max hp per slot
  dec  (play, p_play, top card, tau, no_affordable) or None (frame logs)
  own  my non-tower bodies (cls, X, Y, hp, max_hp)
  P    my plays (tap, land, card, X, Y, el_at_tap, p_play)   land = confirmation tick or None
Own frame tiles: my king (9,3), princesses (3.5,6.5)/(14.5,6.5); my half y <= 16.  Public information only.
"""
import os, sys, glob, gzip, pickle, time, collections, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
MAIN = "C:/Users/benpe/ClashBot/"
sys.path.insert(0, MAIN + "scratchpad/gauntlet/L74/loss_review"); sys.path.insert(0, MAIN)
import review as V            # sets below-normal priority
from pipeline import vocab, body_identity as BI
from pipeline.obs_contract import catalog_card_form

DATA = HERE + "data/"
AIR = {"bats", "bats_evo", "minions", "minion_horde", "minion_horde_evo", "mega_minion", "mega_minion_hero", "baby_dragon", "baby_dragon_evo",
       "inferno_dragon", "inferno_dragon_evo", "electro_dragon", "electro_dragon_evo", "balloon", "balloon_hero", "lava_hound", "lava_pups",
       "skeleton_dragons", "phoenix", "skeleton_barrel", "skeleton_barrel_evo", "flying_machine", "spirit_empress_air"}
# children / sub-spawns not in unit_values.json (elixir per body)
CHILD = {"golemite": 1.0, "elixir_golemite": 0.75, "elixir_blob": 0.375, "lava_pups": 0.3, "royal_recruit": 1.167, "mother_witch_hog": 1.0,
         "skeletons": 0.333, "bats": 0.4, "goblins": 0.5, "spear_goblins": 0.667, "barbarians": 1.0, "guards": 1.0}
VAL = {}


def load_values():
    names, costs, uv = V._catalog(); V.NAME.update(names); V.NCOST.update(costs); V.UV.update(uv)
    for n, c in costs.items():
        k = vocab.engine_key(n)
        if k: VAL.setdefault(k, float(c))
    for n, v in uv.items():
        k = vocab.engine_key(n)
        if k: VAL[k] = float(v)
    VAL.update(CHILD)


def cval(cls):
    n = vocab.UNIT_VOCAB[cls]
    if n in VAL: return VAL[n]
    return VAL.get(vocab.base_key(n), 1.0)


def one(f):
    r = V.parse(f)
    if not (r["end"] or r["stop"]) or len(r["S"]) < 20: return None
    row = V.features(r)
    if not row.get("valid_state") or row.get("dry_run"): return None
    S = r["S"]
    st = r["start"] or {}; do = st.get("decision_options") or {}
    # tower level factor per side (obs_contract: max_hp / 3052 princess, / 4824 king)
    fac = {}
    for s in S[:5]:
        for b in s[4]:
            if b[3] == -1 and b[5] and b[5] > 0:
                fac.setdefault(1 if b[0] else 0, b[5] / (4824.0 if b[6] == 12 else 3052.0))
    first = {}; twmax = {}; seen_tw = set(); NS = []
    for s in S:
        t, el, _, hand, bodies, proj, dec = s
        tw = {}; pend = []; own = []
        for b in bodies:
            mine, X, Y, cid, hp, mx, kind, addr = b
            if cid == -1 and kind in (12, 13):
                sl = V.tower_slot(b)
                if sl and hp > 0: tw[sl] = hp; twmax[sl] = mx
                continue
            if hp is not None and hp <= 0 and (mx or 0) > 0: continue
            if mine:
                n, fm = catalog_card_form(cid)
                own.append((vocab.engine_key(n) if n else str(cid), round(X, 2), round(Y, 2), hp, mx)); continue
            n, fm = catalog_card_form(cid)
            pend.append((X, Y, n or str(cid), mx, fm, cid == -1 or n is None, addr, hp))
        ids = BI.resolve_board([(0, p[2], p[3], p[4], p[5]) for p in pend], {0: fac.get(0, 1.0)}) if pend else []
        eb = []
        for p, idn in zip(pend, ids):
            if idn.cls is None: continue
            X, Y = p[0], p[1]
            if (p[6], idn.cls) not in first: first[(p[6], idn.cls)] = t
            hpf = (p[7] / p[3]) if p[3] and p[3] > 0 and p[7] is not None else None
            nm = vocab.UNIT_VOCAB[idn.cls]
            eb.append((nm, round(X, 2), round(Y, 2), round(cval(idn.cls), 3), p[6], first[(p[6], idn.cls)], hpf, nm in AIR))
        seen_tw |= set(tw)
        for k in seen_tw: tw.setdefault(k, 0)
        pr = [(V.nm(q[3]), round(q[1], 2), round(q[2], 2)) for q in proj if not q[0] and q[3] != -1]
        d = None if dec is None else (dec[0], dec[1], dec[2], dec[3] or .35, dec[4])
        NS.append((t, el, tuple(hand) if hand else None, eb, tw, d, own, pr))
    P = []
    for p in r["plays"]:
        if p["X"] is None: continue
        P.append((p["tick"], p["conf"]["tick"] if p["conf"] else None, p["name"], round(p["X"], 2), round(p["Y"], 2), p["el"], p.get("p")))
    gate = do.get("gate_decode"); ck = row.get("ckpt") or ""
    fam = ("towerref_bundle" if gate else "towerref_pre") if "towerref_w2" in ck else V.family(row)
    return dict(file=r["file"], fam=fam, ckpt=ck, side=r["side"], end=row["end_tick"], S=NS, P=P, twmax=twmax, src_state=r["state_src"],
                row={k: row.get(k) for k in ("file", "ts", "wall_s", "end_tick", "derived", "crowns_me", "crowns_opp", "n_plays", "dry_run", "opp_cards")})


def main():
    load_values()
    fs = sorted(glob.glob(V.LOGDIR + "live_play_2026*.jsonl")); now = time.time()
    fs = [f for f in fs if now - os.path.getmtime(f) >= 600]
    out = []; t0 = time.time(); err = 0
    for i, f in enumerate(fs):
        try: m = one(f)
        except Exception as e:
            err += 1; print("ERR", os.path.basename(f), type(e).__name__, e, flush=True); continue
        if m: out.append(m)
        if i % 100 == 0: print(f"[{i}/{len(fs)}] {time.time() - t0:.0f}s kept {len(out)}", flush=True)
    rows = [m["row"] for m in out]; V.resolve(rows)
    for m, r in zip(out, rows): m["res"] = r["result"]; m["res_src"] = r["result_src"]
    os.makedirs(DATA, exist_ok=True)
    with gzip.open(DATA + "live.pkl.gz", "wb") as fh: pickle.dump(out, fh)
    print("kept", len(out), "errors", err, collections.Counter(m["fam"] for m in out), collections.Counter(m["res"] for m in out),
          collections.Counter(m["src_state"] for m in out))
    unk = collections.Counter(b[0] for m in out for s in m["S"] for b in s[3] if b[0] not in VAL and vocab.base_key(b[0]) not in VAL)
    print("classes valued by fallback 1.0:", unk.most_common(20))


if __name__ == "__main__":
    main()
