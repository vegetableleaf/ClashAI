"""F1c-2: field-by-field agreement of the cue inputs between RoyaleSim fin16 and the crforge facade, on matched scenarios
(the same cards given at the same ticks to both engines; both run every command 20 ticks after it is given).

  fields  N scenarios = census pairs (decks.tsv: icebow vs the 223 opponent decks, their forms), both seats scripted
          (below), T ticks each. Every S ticks: pipeline.sim_unit_state.extract on both engines' ``_battle`` (per-match
          memo, hit window 100 ms as e1_eval.sim_cue_rows calls it) plus the state_json entity rows (ENTITY_FIELDS).
          Bodies are paired across engines by (team, card id, kind, body name), nearest first within PAIR_TILES; towers by
          (team, slot). Per field: compared / equal, split by how far the pair stands apart (in sync = < SYNC_TILES:
          the engines agree on the board there, so a mismatch is the field's mapping, not the fight), and the top
          mismatching value pairs with the body name.
  e1      M matched matches through RoyaleSelfPlayEnv (the pipeline's env, forms_mode deck, levels 16) on each core:
          the same scripted plays (env.act), and at every 10-tick decision side 0's tokens (obs_contract
          from_engine + to_tokens, exact view) and e1_eval.sim_cue_rows on them: the cue tensor the model takes.
          Tokens are paired across engines by (ownership, class, nearest position); per cue column agreement and
          whole-row agreement.

The script: seat 1 (Red) attacks, seat 0 (Blue) answers. Seat 1 gives hand slot k % 4 at ticks 120 + 160 k, seat 0 hand
slot k % 4 at 40 ticks later; both seats press ability buttons 0 / 1 every 150 ticks from tick 300 / 375 (fields
part; a press refused in one engine and given in the other is counted, not a stop). Lane (left / right) from a per-scenario Random. Troops: Red at its bridge (y 18.5), Blue
in front of its tower (y 10.5); buildings 3 tiles behind; spells on the other seat's last troop placement, 2.5 tiles
toward the caster (a Rocket / Log / Tornado lands on what walked there). Plays are engine independent; a play one engine
gives and the other refuses ends the scenario's comparison there (counted).

usage (pod 30408): ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I cue_ab.py fields|e1 [--n N] --out FILE
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB", "/workspace/f1c/cb")]

import numpy as np  # noqa: E402

from pipeline.crforge_core import CrforgeCore  # noqa: E402
from pipeline import royale_heroiw as heroiw  # noqa: E402
from pipeline.sim_unit_state import extract  # noqa: E402
from royalesim import STATUS_BITS  # noqa: E402
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

DECKS = Path("/workspace/cfspeed/decks.tsv")
SFX = {0: "", 1: "@evolution", 2: "@hero"}
PAIR_TILES, SYNC_TILES = 1.5, 0.25
LANES = (3.5, 14.5)
TOP = 12
PRESS_FROM = 300          # every side presses ability button 0 at 300 + 150 k, button 1 at 375 + 150 k (both engines)
ROW_FIELDS = ("deploy_ticks", "stun_ticks", "knockback_ticks", "attack_phase", "charge", "shield", "status_flags",
              "flying", "radius", "level", "hp", "max_hp", "facing", "mount_uid", "dest_x", "dest_y", "ability_ticks",
              "footprint")


def census():
    out = []
    for line in DECKS.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            f = line.split("\t")
            out.append((f[1].split(","), [int(v) for v in f[2].split(",")], f[3].split(","), [int(v) for v in f[4].split(",")]))
    return out


class Script:
    """Engine-independent plays: (tick, side, slot, x, y) in tiles, from the card kinds of the hand at that tick."""

    def __init__(self, seed, kinds):
        self.rng, self.kinds, self.k, self.last = random.Random(seed), kinds, [0, 0], {0: None, 1: None}
        self.lane = LANES[0]

    def due(self, tick):
        out = []
        for side, off in ((1, 120), (0, 160)):
            if tick >= off and (tick - off) % 160 == 0:
                out.append(side)
        return out

    def place(self, side, card):
        kind = self.kinds[card]
        if side == 1:
            self.lane = LANES[self.rng.randrange(2)]
        if kind == "SPELL":
            tgt = self.last[1 - side]
            if tgt is None:                       # nothing placed yet: the other seat's princess tower on this lane
                tgt = (self.lane, 25.5 if side == 0 else 6.5)
            return tgt[0], tgt[1] + (2.5 if side == 1 else -2.5)
        y = (18.5 if side == 1 else 10.5) + (3.0 if side == 1 else -3.0) * (kind == "BUILDING")
        x = self.lane if kind != "BUILDING" else 9.0 + (self.lane - 9.0) / 3
        self.last[side] = (x, y)
        return x, y


# ------------------------------------------------------------------------------------------------ comparison helpers
class Tally:
    def __init__(self):
        self.n = collections.Counter()
        self.eq = collections.Counter()
        self.bad = collections.defaultdict(collections.Counter)

    def add(self, field, a, b, sync, who, body=True):
        for scope in ("all",) + (("sync",) if sync else ()) + (("body_sync",) if sync and body else ()):
            self.n[field, scope] += 1
            self.eq[field, scope] += a == b
        if a != b:
            self.bad[field][f"rs={json.dumps(a, default=str)[:60]} cf={json.dumps(b, default=str)[:60]} | {who}"] += 1

    def table(self):
        fields = sorted({f for f, _ in self.n})
        rows = []
        for f in fields:
            r = {"field": f}
            for scope in ("all", "sync", "body_sync"):
                n = self.n[f, scope]
                r[scope] = {"n": n, "equal": self.eq[f, scope], "rate": round(self.eq[f, scope] / n, 4) if n else None}
            r["top_mismatch"] = self.bad[f].most_common(TOP)
            rows.append(r)
        return rows


def rows_by_uid(battle):
    import royalesim
    st = json.loads(battle.state_json())
    return {r[0]: dict(zip(royalesim.ENTITY_FIELDS, r)) for r in st["entities"]}


def pair_units(ua, ub, ra, rb):
    """[(a, b, dist)] by (team, card id, kind, body name) nearest-first within PAIR_TILES; towers by (team, kind, x side)."""
    def key(u, rows):
        r = rows[u["uid"]]
        if u["kind"] in ("princess_tower", "king_tower"):
            return ("T", u["team"], u["kind"], u["x"] < 9)
        return ("U", u["team"], r["card_id"], u["kind"], u["name"])
    ga, gb = collections.defaultdict(list), collections.defaultdict(list)
    for u in ua:
        ga[key(u, ra)].append(u)
    for u in ub:
        gb[key(u, rb)].append(u)
    out = []
    for k, la in ga.items():
        lb = gb.get(k, [])
        cand = sorted((float(np.hypot(a["x"] - b["x"], a["y"] - b["y"])), i, j)
                      for i, a in enumerate(la) for j, b in enumerate(lb))
        used_a, used_b = set(), set()
        for d, i, j in cand:
            if d > PAIR_TILES and k[0] == "U":
                break
            if i in used_a or j in used_b:
                continue
            used_a.add(i), used_b.add(j)
            out.append((la[i], lb[j], d))
    return out


def canon_buffs(buffs, alias_of):
    return sorted(alias_of.get(b["name"], b["name"]) for b in buffs)


def compare_tick(T, ca, cb, ra, rb, alias_of, counts):
    pairs = pair_units(ca["units"], cb["units"], ra, rb)
    counts["units_rs"] += len(ca["units"])
    counts["units_cf"] += len(cb["units"])
    counts["paired"] += len(pairs)
    a2b = {a["uid"]: b["uid"] for a, b, _ in pairs}
    for a in ca["units"]:
        for bf in a["buffs"]:
            for nm in bf["name"].split("|"):
                alias_of.setdefault(nm, bf["name"])
    for a, b, d in pairs:
        sync = d < SYNC_TILES
        who = a["name"] + ("/" + b["name"] if b["name"] != a["name"] else "")
        body = a["kind"] not in ("princess_tower", "king_tower")
        add = lambda f, x, y: T.add(f, x, y, sync, who, body)  # noqa: E731
        add("name", a["name"], b["name"])
        for f in ("state", "charging", "charge_frac", "hide"):
            add(f, a[f], b[f])
        aa, ab = a["attack"], b["attack"]
        ta = aa["target"]
        add("attack.target", None if ta is None else a2b.get(ta, "unpaired"), ab["target"])
        add("attack.has_target", ta is not None, ab["target"] is not None)
        for f in ("phase", "frac", "progress_ms", "hit_speed_ms", "load_ms"):
            add("attack." + f, aa[f], ab[f])
        for f, v in a["status"].items():
            add("status." + f, v, b["status"][f])
        add("buffs.names", canon_buffs(a["buffs"], alias_of), canon_buffs(b["buffs"], alias_of))
        add("buffs.ms", sorted(x["ms"] for x in a["buffs"]), sorted(x["ms"] for x in b["buffs"]))
        xa, xb = ra[a["uid"]], rb[b["uid"]]
        for f in ROW_FIELDS:
            va, vb = xa[f], xb[f]
            if f == "mount_uid":
                va = -1 if va == -1 else a2b.get(va, "unpaired")
            add("row." + f, va, vb)
        fa, fb = xa["status_flags"], xb["status_flags"]
        for bit, nm in enumerate(STATUS_BITS):          # per bit, over the rows where either engine sets it
            if (fa | fb) >> bit & 1:
                add("bit." + nm, bool(fa >> bit & 1), bool(fb >> bit & 1))
    # shots: by (team, source pairing) nearest
    used = set()
    for p in ca["projectiles"]:
        best = None
        for j, q in enumerate(cb["projectiles"]):
            if j in used or q["team"] != p["team"]:
                continue
            d = float(np.hypot(p["x"] - q["x"], p["y"] - q["y"]))
            if d <= PAIR_TILES and (best is None or d < best[0]):
                best = (d, j, q)
        counts["shots_rs"] += 1
        if best is None:
            continue
        d, j, q = best
        used.add(j)
        counts["shots_paired"] += 1
        who = str(p["type"])
        T.add("shot.type", p["type"], q["type"], d < SYNC_TILES, who)
        T.add("shot.source", None if p["source"] is None else a2b.get(p["source"], "unpaired"), q["source"], d < SYNC_TILES, who)
        T.add("shot.target", None if p["target"] is None else a2b.get(p["target"], "unpaired"), q["target"], d < SYNC_TILES, who)
        T.add("shot.effect", p["effect"], q["effect"], d < SYNC_TILES, who)
        T.add("shot.damage", p["damage"], q["damage"], d < SYNC_TILES, who)
    counts["shots_cf"] += len(cb["projectiles"])
    used = set()
    for s in ca["areas"]:
        counts["areas_rs"] += 1
        cand = [(float(np.hypot(s["x"] - q["x"], s["y"] - q["y"])), j, q) for j, q in enumerate(cb["areas"])
                if j not in used and q["team"] == s["team"] and q["name"] == s["name"]]
        if not cand:
            continue
        d, j, q = min(cand, key=lambda c: c[0])
        if d > PAIR_TILES:
            continue
        used.add(j)
        counts["areas_paired"] += 1
        for f in ("motion", "remaining_ms", "frac"):
            T.add("area." + f, s[f], q[f], d < SYNC_TILES, s["name"])
    counts["areas_cf"] += len(cb["areas"])


# ------------------------------------------------------------------------------------------------ part: fields
def part_fields(a):
    pairs = census()
    rs = RustEngine(**heroiw.engine_options())
    rs.set_command_delay_ticks(20)
    cf = CrforgeCore()
    ids = {c.name: c.card_id for c in rs.cards()}
    kinds = {c.card_id: c.card_kind for c in rs.cards()}
    T, counts, alias_of, per = Tally(), collections.Counter(), {}, []
    t0 = time.time()
    for i in range(a.n):
        d0, f0, d1, f1 = pairs[i % len(pairs)]
        setup = MatchSetup(decks=[[ids[n] for n in d0], [ids[n] for n in d1]], shuffle=ShuffleMode.NONE, forms=[f0, f1],
                           levels=[[16] * 8, [16] * 8], tower_levels=[16, 16])
        try:
            rs.reset(1000 + i, setup)
        except ValueError as exc:           # a form RoyaleSim does not load (ElectroWizard hero ...): skip the pair
            per.append({"i": i, "opp": d1, "skipped": repr(exc)[:200]})
            continue
        cf.reset(1000 + i, setup)
        sc = Script(i, kinds)
        ma, mb, end, why = {}, {}, a.ticks, "ticks"
        plays = collections.Counter()
        for tick in range(0, a.ticks, a.every):
            cmds = []
            for side in sc.due(tick):
                k = sc.k[side]
                sc.k[side] += 1
                slot = k % 4
                card = rs.state().players[side].hand[slot]
                if card < 0:
                    continue
                x, y = sc.place(side, card)
                cmds.append(DeployCommand(side, slot, int(x * 18000), int(y * 18000)))
            if cmds:
                hand_a = [list(p.hand) for p in rs.state().players]
                hand_b = [list(p.hand) for p in cf.state().players]
                if hand_a != hand_b:
                    end, why = tick, "hand_differs"
                    break
            presses = [DeployCommand(side, 4 + b, 0, 0) for side in (0, 1) for b in (0, 1)
                       if tick >= PRESS_FROM and (tick - PRESS_FROM - 75 * b) % 150 == 0]
            res_a = rs.step(cmds + presses, a.every)
            res_b = cf.step(cmds + presses, a.every)
            n = len(cmds)
            if [r.status for r in res_a[:n]] != [r.status for r in res_b[:n]]:
                end, why = tick, f"status {[int(r.status) for r in res_a]} vs {[int(r.status) for r in res_b]}"
                break
            for r in res_a[:n]:
                plays[int(r.status)] += 1
            for ra, rb in zip(res_a[n:], res_b[n:]):    # ability presses (hero / champion buttons): not a stop
                counts["press_same" if ra.status == rb.status else "press_differs"] += 1
                counts["press_ok_rs"] += ra.status == 0
                counts["press_ok_cf"] += rb.status == 0
            sa, sb = rs.state(), cf.state()
            if sa.game_over or sb.game_over:
                end, why = tick, "game_over"
                break
            ca, cb = extract(rs._battle, ma, hit_window_ms=100), extract(cf._battle, mb, hit_window_ms=100)
            compare_tick(T, ca, cb, rows_by_uid(rs._battle), rows_by_uid(cf._battle), alias_of, counts)
            counts["samples"] += 1
        per.append({"i": i, "opp": d1, "forms": f1, "end": end, "why": why, "plays": dict(plays)})
        if i % 20 == 0:
            print(json.dumps({"i": i, "s": round(time.time() - t0, 1), **dict(counts)}), flush=True)
    cards_rs = sorted({n for d0, _, d1, _ in pairs[:a.n] for n in d0 + d1})
    return dict(scenarios=len(per), compared=sum(1 for p in per if "skipped" not in p), counts=dict(counts),
                cards=cards_rs, fields=T.table(), scenarios_rows=per, wall_s=round(time.time() - t0, 1),
                cf_unmapped=cf.unmapped()["missing"])


# ------------------------------------------------------------------------------------------------ part: e1 cue tensors
def part_e1(a):
    from pipeline import e1_eval as E
    from pipeline.model_gen import CUE_N
    from pipeline.obs_contract import from_engine, load_deck, to_tokens
    from pipeline.royale_env import RoyaleSelfPlayEnv
    deck = load_deck("icebow")
    pairs = census()
    lv = {"cards": [[16] * 8, [16] * 8], "towers": [16, 16]}
    col_n, col_eq = np.zeros(CUE_N, np.int64), np.zeros(CUE_N, np.int64)
    rows_n = rows_eq = known_a = known_b = tok_a = tok_b = paired = 0
    bad = collections.defaultdict(collections.Counter)
    per, t0 = [], time.time()
    for i in range(a.n):
        d0, f0, d1, f1 = pairs[(5 * i) % len(pairs)]
        envs = []
        for eng in ("rs", "cf"):
            env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=1)
            if eng == "cf":
                env.core = CrforgeCore()
                env.engine_delay_ticks = 20
            else:
                env.core.set_command_delay_ticks(20)
            envs.append(env)
        try:
            for env in envs:
                env.reset([n + SFX[f] for n, f in zip(d0, f0)], [n + SFX[f] for n, f in zip(d1, f1)], seed=4000 + i, levels=lv)
        except Exception as exc:
            per.append({"i": i, "opp": d1, "skipped": repr(exc)[:200]})
            continue
        kinds = {c.card_id: c.card_kind for c in envs[0].core.cards()}
        sc = Script(10_000 + i, kinds)
        dec, why, played = 0, "end", 0
        while not (envs[0].done or envs[1].done):
            tick = envs[0].tick
            if envs[1].tick != tick:
                why = "tick_differs"
                break
            ok = True
            for side in sc.due(tick - tick % 10):
                k = sc.k[side]
                sc.k[side] += 1
                hand = envs[0].core.state().players[side].hand
                if hand != envs[1].core.state().players[side].hand:
                    ok, why = False, "hand_differs"
                    break
                cid = hand[k % 4]
                if cid < 0:
                    continue
                x, y = sc.place(side, cid)
                di = envs[0].deck_ids[side].index(cid)
                r = [env.act(side, di, int(x * 1000), int(y * 1000))["accepted"] for env in envs]
                played += r[0]
                if r[0] != r[1]:
                    ok, why = False, f"accept {r}"
                    break
            if not ok:
                break
            for env in envs:
                env.advance_to(tick + 10)
            cues, toks = [], []
            for env in envs:
                raw = env.raw()
                bs = from_engine(raw, 0, deck, engine_deck=env.decks[0] if hasattr(env, "decks") else None)
                tok, mask, _ = to_tokens(bs, E.MAX_U)
                cues.append(E.sim_cue_rows(SimpleNamespace(_obs=(tok, mask), env=env, side=0)))
                toks.append((tok, mask))
            dec += 1
            (ta, ma), (tb, mb) = toks
            ia = np.flatnonzero(ma & (ta[:, 13] == 0))
            ib = np.flatnonzero(mb & (tb[:, 13] == 0))
            tok_a += len(ia)
            tok_b += len(ib)
            known_a += int(cues[0][ia, 0].sum())
            known_b += int(cues[1][ib, 0].sum())
            cand = sorted((float(np.hypot((ta[p, 4] - tb[q, 4]) * 18, (ta[p, 5] - tb[q, 5]) * 32)), p, q)
                          for p in ia for q in ib if ta[p, 1] == tb[q, 1] and ta[p, 2] == tb[q, 2] and ta[p, 0] == tb[q, 0])
            ua, ub = set(), set()
            for d, p, q in cand:
                if d > SYNC_TILES:
                    break
                if p in ua or q in ub:
                    continue
                ua.add(p), ub.add(q)
                paired += 1
                va, vb = cues[0][p], cues[1][q]
                eq = va == vb
                col_n += 1
                col_eq += eq
                rows_n += 1
                rows_eq += bool(eq.all())
                if not eq.all():
                    who = body_name(envs[0], ta[p])
                    for c in np.flatnonzero(~eq):
                        bad[int(c)][f"rs={va[c]:.3f} cf={vb[c]:.3f} | {who}"] += 1
        per.append({"i": i, "opp": d1, "decisions": dec, "plays_accepted": played, "end_tick": int(envs[0].tick), "why": why})
        print(json.dumps(per[-1]), flush=True)
    names = (["cue_known"] + [f"state={s}" for s in E_states()] + ["charging", "tesla_hidden", "has_target",
             "target_is_tower"] + [f"phase={p}" for p in E_phases()] + ["attack_frac"] + [f"status.{s}" for s in E_status()]
             + ["slow_frac"])
    cols = [{"col": names[c] if c < len(names) else c, "n": int(col_n[c]), "equal": int(col_eq[c]),
             "rate": round(col_eq[c] / col_n[c], 4) if col_n[c] else None, "top_mismatch": bad[c].most_common(6)}
            for c in range(CUE_N)]
    return dict(matches=sum(1 for p in per if "skipped" not in p), rows=per, unit_tokens={"rs": tok_a, "cf": tok_b},
                cue_known={"rs": known_a, "cf": known_b}, paired_tokens=paired,
                row_agreement={"n": rows_n, "equal": rows_eq, "rate": round(rows_eq / rows_n, 4) if rows_n else None},
                columns=cols, wall_s=round(time.time() - t0, 1))


def body_name(env, tok):
    """Name of the RoyaleSim body nearest a side-0 token (sim_cue_rows' frame): for the mismatch listing only."""
    c = extract(env.core._battle, None)
    best = min(((np.hypot(u["x"] / 18.0 - tok[4], (1.0 - u["y"] / 32.0) - tok[5]), u["name"]) for u in c["units"]
                if u["kind"] not in ("princess_tower", "king_tower")), default=(None, None))
    return best[1]


def E_states():
    from pipeline.model_gen import CUE_STATES
    return CUE_STATES


def E_phases():
    from pipeline.model_gen import CUE_PHASES
    return CUE_PHASES


def E_status():
    from pipeline.model_gen import CUE_STATUS
    return CUE_STATUS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=("fields", "e1"))
    ap.add_argument("--n", type=int, default=223)
    ap.add_argument("--ticks", type=int, default=1200)
    ap.add_argument("--every", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = dict(part=a.part, n=a.n, ticks=a.ticks, every=a.every, result=globals()[f"part_{a.part}"](a))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    r = out["result"]
    if a.part == "fields":
        for row in r["fields"]:
            s, y, z = row["all"], row["sync"], row["body_sync"]
            print(f"{row['field']:20s} all {s['rate']} (n {s['n']})  sync {y['rate']} (n {y['n']})  body {z['rate']} (n {z['n']})  "
                  f"{row['top_mismatch'][:2]}"[:300])
        print(json.dumps(r["counts"]))
    else:
        print(json.dumps({k: v for k, v in r.items() if k not in ("rows", "columns")}))
        for c in r["columns"]:
            print(c["col"], c["rate"], c["n"], c["top_mismatch"][:3])


if __name__ == "__main__":
    main()
