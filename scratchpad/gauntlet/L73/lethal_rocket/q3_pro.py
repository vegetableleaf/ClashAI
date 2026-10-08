"""Q3: pro behaviour with a LETHAL Rocket available (gen_dataset_v32_fv5 pro rows), and how the live checkpoint scores
those rows.  python q3_pro.py <npz> <ckpt>   (VM; CPU)
Lethal: an alive, HP-known enemy princess at hp_frac <= 497/4424 (= Rocket crown damage / princess max HP at level 15;
level 11 gives 342/3052 = same 11.2 %; pro card / tower levels are not in the rows, so equal levels are ASSUMED), Rocket
in hand, own elixir >= 6. Opportunity = the first such row of a stretch (rows of one replay side, gaps <= 3 s).
Outcome = the pro's first play within 3 s / 10 s: Rocket on a lethal tower (aim within 3 tiles = Rocket radius 2 +
princess radius 1 of its centre), Rocket elsewhere, another card, or no play."""
import ast, json, sys, os, zipfile
from collections import Counter
import numpy as np
import torch

NPZ, CKPT = sys.argv[1], sys.argv[2]
THR = 497 / 4424
z = np.load(NPZ)
meta = json.loads(str(z["meta"]))
CV = ast.literal_eval(meta["card_vocab"]) if isinstance(meta["card_vocab"], str) else meta["card_vocab"]
RK = CV.index("rocket")
tick, side, rep, deck = z["tick"], z["side"], z["rep"], z["deck_id"]
gate, ycard, yxy, hand = z["y_gate"], z["y_card"], z["y_xy"], z["hand_card"]
sc = z["sc"]
el = sc[:, 3] * 10
hpL, hpR = sc[:, 56], sc[:, 57]
okL = (sc[:, 68] > .5) & (sc[:, 62] > .5) & (hpL > 0) & (hpL <= THR)
okR = (sc[:, 69] > .5) & (sc[:, 63] > .5) & (hpR > 0) & (hpR <= THR)
has_rk = (hand == RK).any(1)
cond = (okL | okR) & has_rk & (el >= 6)
print(f"rows {len(tick)}; rocket gid {RK}; lethal-princess rows {int((okL | okR).sum())}; +Rocket in hand "
      f"{int(((okL | okR) & has_rk).sum())}; +elixir>=6 {int(cond.sum())}")

order = np.lexsort((tick, side, rep))
TX = {"L": 3.5, "R": 14.5}


def aim_lane(xy):
    x, y = xy[0] * 18, xy[1] * 32
    for lane, tx in TX.items():
        if np.hypot(x - tx, y - 6.5) <= 3.0:
            return lane
    return None


opps = []      # (row, phase, lanes, outcome3, outcome10, first_card10, deck)
o_rep, o_side, o_tick = rep[order], side[order], tick[order]
grp_start = np.r_[True, (o_rep[1:] != o_rep[:-1]) | (o_side[1:] != o_side[:-1])]
gid_ = np.cumsum(grp_start) - 1
bounds = np.r_[np.flatnonzero(grp_start), len(order)]
for g in range(len(bounds) - 1):
    rows_g = order[bounds[g]:bounds[g + 1]]
    prev_cond = -10 ** 9
    for k, r in enumerate(rows_g):
        if not cond[r]:
            continue
        start = tick[r] - prev_cond > 60          # a new stretch: no lethal-available row in the previous 3 s
        prev_cond = tick[r]
        if not start:
            continue
        lanes = {l for l, ok in (("L", okL[r]), ("R", okR[r])) if ok}
        t0 = tick[r]
        plays = [q for q in rows_g[k:] if gate[q] == 1 and tick[q] - t0 <= 200]
        first = plays[0] if plays else None
        out = {}
        for win, lim in (("3s", 60), ("10s", 200)):
            if first is not None and tick[first] - t0 <= lim:
                out[win] = (("rocket_lethal" if aim_lane(yxy[first]) in lanes else "rocket_elsewhere")
                            if ycard[first] == RK else "other_card")
            else:
                out[win] = "no_play"
        # any Rocket on a lethal tower within 10 s, even if not the first play
        any10 = any(ycard[q] == RK and aim_lane(yxy[q]) in lanes for q in plays)
        opps.append((r, "OT" if t0 >= 3600 else "reg", "".join(sorted(lanes)), out["3s"], out["10s"],
                     CV[ycard[first]] if first is not None else None, int(deck[r]), any10))

ICEBOW = 90
for label, sel in (("all decks", lambda o: True), ("deck 90 (icebow)", lambda o: o[6] == ICEBOW)):
    for ph in ("OT", "reg"):
        rows = [o for o in opps if o[1] == ph and sel(o)]
        c3, c10 = Counter(o[3] for o in rows), Counter(o[4] for o in rows)
        other = Counter(o[5] for o in rows if o[4] == "other_card")
        print(f"[{label}] {ph}: opportunities {len(rows)} (replay sides {len({(rep[o[0]], side[o[0]]) for o in rows})}); "
              f"within 3 s {dict(c3)}; within 10 s {dict(c10)}; rate Rocket-on-lethal 3 s "
              f"{c3['rocket_lethal'] / max(1, len(rows)):.3f} / 10 s {c10['rocket_lethal'] / max(1, len(rows)):.3f}; "
              f"any lethal Rocket within 10 s {sum(o[7] for o in rows) / max(1, len(rows)):.3f}; "
              f"other first cards {other.most_common(6)}")

# ---- when pros do NOT Rocket the lethal tower within 10 s: did it fall anyway (within 10 / 20 s), and outcomes ----
ycr = z["y_crowns"]
alive_col = {"L": 68, "R": 69}
for label, sel in (("all decks", lambda o: True), ("deck 90 (icebow)", lambda o: o[6] == ICEBOW)):
    for ph in ("OT",):
        rows = [o for o in opps if o[1] == ph and sel(o)]
        for grp_name, grp in (("lethal Rocket <=10 s", [o for o in rows if o[7]]),
                              ("no lethal Rocket <=10 s", [o for o in rows if not o[7]])):
            fell10 = fell20 = won = 0
            for o in grp:      # OT = sudden death: the first tower down ends the match, so no later rows exist;
                r = o[0]       # proxy = the pro WON and the replay side's rows end within 10 / 20 s
                last = tick[(rep == rep[r]) & (side == side[r])].max()
                w = ycr[r, 0] > ycr[r, 1]
                won += w
                fell10 += w and last - tick[r] <= 200
                fell20 += w and last - tick[r] <= 400
            n_ = max(1, len(grp))
            print(f"[{label}] OT {grp_name}: n {len(grp)}; pro won with the match ending within 10 s {fell10 / n_:.3f}, "
                  f"20 s {fell20 / n_:.3f}; pro won the match {won / n_:.3f}")

# ---- live checkpoint on the OT opportunity rows (all decks with Rocket; deck 90 reported separately) ----
sys.path.insert(0, os.environ.get("CB_REPO", "."))
from pipeline.model_gen import load_model
from pipeline.eval_gen import GenRows
from pipeline.e1_eval import allowed_slots
from pipeline.opp_elixir_count import card_cost
from pipeline.decision_options import rocket_area_scores

KEYS = ["sc", "hand_card", "hand_form", "next_card", "next_form", "deck_card", "deck_form", "past", "y_gate", "y_card",
        "y_hand_pos", "y_xy", "y_wait_card", "y_wait_dt", "y_crowns", "tick", "side", "rep", "split", "deck_id",
        "opp_past", "opp_cycle", "projectiles", "effects", "own_ability", "y_cell"]


def take(zf, name, idx):
    idx = np.asarray(idx)
    with zf.open(name + ".npy") as f:
        ver = np.lib.format.read_magic(f)
        shape, _, dt = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0) else np.lib.format.read_array_header_2_0(f))
        rb = int(np.prod(shape[1:], dtype=np.int64)) * dt.itemsize
        out = np.empty((len(idx),) + tuple(shape[1:]), dt); step = max(1, (96 << 20) // max(rb, 1)); o = 0
        for lo in range(0, shape[0], step):
            m = min(step, shape[0] - lo); buf = bytearray()
            while len(buf) < m * rb:
                c = f.read(m * rb - len(buf))
                if not c:
                    raise EOFError(name)
                buf += c
            a, b = np.searchsorted(idx, [lo, lo + m])
            if b > a:
                out[o:o + b - a] = np.frombuffer(buf, dt).reshape((m,) + tuple(shape[1:]))[idx[a:b] - lo]; o += b - a
    return out


for ph in (() if os.environ.get("NO_MODEL") else ("OT", "reg")):
    sel = np.array(sorted(o[0] for o in opps if o[1] == ph))
    if not len(sel):
        continue
    zf = zipfile.ZipFile(NPZ)
    sub = {k: take(zf, k, sel) for k in KEYS}
    off = z["off"]; lens = off[sel + 1] - off[sel]
    gather = np.concatenate([np.arange(off[i], off[i + 1]) for i in sel])
    sub["tok"] = take(zf, "tok", gather); sub["unit_form"] = take(zf, "unit_form", gather)
    sub["off"] = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    dev = torch.device("cpu")
    model, st = load_model(CKPT, dev); model.eval()
    assert st["card_vocab"] == CV, "checkpoint card vocab differs from the dataset's"
    rows = GenRows(sub, np.arange(len(sel)), dev)
    COST = np.array([0.0] + [card_cost(c.replace("-", "_")) or 0.0 for c in CV[1:]])
    lane_of = {o[0]: o[2] for o in opps}
    is90 = sub["deck_id"] == ICEBOW
    R = dict(p=[], prk=[], top_rk=[], mass_lethal=[], area_lethal=[], live_fire=[])
    c = np.arange(2304); CX, CY = (c % 36) * .5, (c // 36) * .5
    tau = .55 if ph == "OT" else .35
    with torch.no_grad():
        for s in range(0, len(sel), 256):
            ids = np.arange(s, min(s + 256, len(sel)))
            b = rows.batch(ids)
            o = model(b)
            p = torch.sigmoid(o["gate"].float()).numpy()
            h = sub["hand_card"][ids].astype(int)
            aff = (h > 0) & (COST[h] <= np.floor(sub["sc"][ids, 3] * 10 + 1e-3)[:, None] + 1e-6)
            lg = np.where(aff, o["card"].float().numpy(), -np.inf)
            P = np.exp(lg - lg.max(1, keepdims=True)); P /= P.sum(1, keepdims=True)
            isr = h == RK
            prk = (P * isr).sum(1); top = isr[np.arange(len(ids)), lg.argmax(1)]
            slot = isr.argmax(1)
            cell = model(b, card=torch.full((len(ids),), RK), form=torch.as_tensor(sub["hand_form"][ids, slot]).long())["cell"]
            pc = torch.softmax(cell.float(), -1)
            area = rocket_area_scores(pc).numpy(); pc = pc.numpy()
            for k, rid in enumerate(ids):
                lanes = lane_of[sel[rid]]
                disk = np.zeros(2304, bool)
                for ln in lanes:
                    disk |= np.hypot(CX - TX[ln], CY - 6.5) <= 3.0
                best = int(area[k].argmax())
                R["mass_lethal"].append(pc[k][disk].sum())
                R["area_lethal"].append(bool(disk[best]))
                R["live_fire"].append(bool(top[k] and p[k] > tau and disk[best]))
            R["p"] += list(p); R["prk"] += list(prk); R["top_rk"] += list(top)
    A = {k: np.asarray(v, float) for k, v in R.items()}
    for label, m in (("all decks", np.ones(len(sel), bool)), ("deck 90", is90)):
        if m.sum():
            print(f"[live ckpt, {ph}, {label}] n {int(m.sum())}: gate p mean {A['p'][m].mean():.3f} (> tau {tau}: "
                  f"{(A['p'][m] > tau).mean():.3f}); P(Rocket) mean {A['prk'][m].mean():.3f}; top card Rocket "
                  f"{A['top_rk'][m].mean():.3f}; Rocket cell mass within 3 tiles of a lethal tower "
                  f"{A['mass_lethal'][m].mean():.3f}; rocket_area cell on a lethal tower {A['area_lethal'][m].mean():.3f}; "
                  f"live-rule would Rocket the lethal tower on this row {A['live_fire'][m].mean():.3f}")
