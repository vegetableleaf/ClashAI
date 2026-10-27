"""S3 step 2 (plan1026 Pillar 4b on crforge): the cost of OUR policy's main observation tensors from crforge state.

Per seat-decision, on the same crforge states (CfSpeed.Rollout, random legal plays every 10 ticks, census decks):
  P1  Python reads every entity through JPype, builds from_engine's raw dict, then obs_contract.from_engine + to_tokens
      + to_unit_forms (pipeline/obs_contract.py, unchanged).
  P2  Java dumps the match into one int[] (CfSpeed.Dump), Python builds the same raw dict, then the same three calls.
  P3  Java builds tok [64,14] / mask [64] / sc [70] / unit_form [64] (CfSpeed.Match.obs) into direct buffers that
      numpy views without a copy.
Identity: P3 == P2's Python tensors, every seat-decision of every env (from_engine feature_version 4: the name + max_hp
vocab path; fv 5/6 add body_identity.resolve_board, timed but not compared).

usage (pod 32657): /workspace/venvf15/bin/python -I cf_obs.py --envs 16 --steps 400 --out runs/obs.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

CF = Path("/workspace/cfspeed")
sys.path[:0] = [str(CF / "pylib"), str(CF / "cb")]

import jpype  # noqa: E402
import numpy as np  # noqa: E402

from pipeline import obs_contract as oc  # noqa: E402
from pipeline import vocab  # noqa: E402

FORM_SUFFIX = (("_EV1", 1), ("_hero", 2), ("Hero", 2))
# crforge body rows whose name is not RoyaleSim's engine spelling (seen 10-27 on the census decks). ponytail: a cost
# probe's alias list, not the naming adapter; the cube's identity follows obs_contract.entity_form (a hero-form body).
ALIAS = {"Skeleton": ("Skeletons", 0), "Barbarian": ("Barbarians", 0), "IceWizardHeroFloatingCube": ("IceWizard", 2)}


def split_form(name: str) -> tuple[str, int]:
    """crforge body row name -> (base row name, form 0 base / 1 evolved / 2 hero)."""
    if name in ALIAS:
        return ALIAS[name]
    for suf, form in FORM_SUFFIX:
        if name.endswith(suf):
            return name[: -len(suf)], form
    return name, 0


def start_jvm(threads: int, xmx: str = "4g"):
    lib = CF / "crforge/env/build/install/env/lib"
    cp = sorted(str(p) for p in lib.glob("*.jar")) + [str(CF / "build")]
    jpype.startJVM(f"-Xmx{xmx}", f"-XX:ActiveProcessorCount={max(threads, 1)}", classpath=cp, convertStrings=True)


def read_decks(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        rows.append((f[1].split(","), [int(v) for v in f[2].split(",")], f[3].split(","), [int(v) for v in f[4].split(",")]))
    return rows


def our_decks(pairs):
    """Per pair: (Deck seat 0, Deck seat 1, engine-index -> our-slot map seat 0, seat 1). Seat 0 is icebow (its yaml
    order); an opponent's 'deck' is its engine order (the map is the identity)."""
    ice = oc.load_deck("icebow")
    out = []
    for d0, _s0, d1, _s1 in pairs:
        m0 = [ice.slot_of(vocab.engine_key(n)) for n in d0]
        if sorted(m0) != list(range(8)):
            raise ValueError(f"seat 0 is not the icebow deck: {d0} -> {m0}")
        cards = tuple(vocab.engine_key(n) or "?" for n in d1)
        ids = tuple(-1 if (c := vocab.engine_unit_id(n)) is None else c for n in d1)
        out.append((ice, dataclasses.replace(ice, name="opp", cards=cards, card_ids=ids), m0, list(range(8))))
    return out


def resolve(names) -> int:
    """Fill the Java name tables for every name the builder met but did not know (pipeline.vocab, as from_engine maps:
    a non-sub-spawn body with any max_hp; a sub-spawn parent with none, so golemites map to their parent: see notes)."""
    k = 0
    for s in names.takeMissing():
        kind, name = s[:2], s[2:]
        if kind == "U:":
            base, form = split_form(name)
            key = vocab.engine_key(base)
            cid = vocab.engine_unit_id(base, None if key in vocab._SUBSPAWN else 1.0)
            names.putUnit(name, -1 if cid is None else int(cid), form)
        else:
            cid = vocab.engine_spell_id(name)
            names.putSpell(name, -1 if cid is None else int(cid))
        k += 1
    return k


def raw_from_dump(d: list, names: list, decks) -> dict:
    """CfSpeed.Dump int[] -> from_engine's raw dict (obs_contract.from_engine docstring)."""
    players = []
    for s in (0, 1):
        hand = [dict(hand_index=h, name=decks[s][d[3 + s * 5 + h]]) for h in range(4) if d[3 + s * 5 + h] >= 0]
        nx = d[7 + s * 5]
        players.append(dict(side=s, elixir_exact=d[1 + s] / 10000.0, hand=hand, next_deck_index=nx if nx >= 0 else None))
    ents, towers, effects = [], [], []
    for at in range(14, len(d), 10):
        typ, ni, side, x, y, hp, mhp, eid, dep, king = d[at:at + 10]
        name = names[ni]
        if typ == 1:
            towers.append(dict(side=side, type="king" if king else "princess", x=x, y=y, hp=hp, max_hp=mhp,
                               destroyed=hp <= 0))
        elif typ == 0:
            base, form = split_form(name)
            ents.append(dict(side=side, x=x, y=y, name=base, hp=hp, max_hp=mhp, card_id=0, kind=12 if dep > 0 else 0,
                             entity_id=eid, status_flags=16 if form == 2 else 8 if form == 1 else 0))
        else:
            effects.append(dict(side=side, x=x, y=y, name=name))
    return dict(tick=d[0], players=players, entities=ents, episode=dict(crown_towers=towers), effects=effects)


class JPypeReader:
    """P1: every field read through JPype, one Java call per field."""

    def __init__(self):
        J = jpype.JClass
        self.World = J("org.crforge.core.battle.unit.WorldEntity")
        self.Tower = J("org.crforge.core.battle.unit.TowerEntity")
        self.Char = J("org.crforge.core.battle.unit.CharacterEntity")
        self.Proj = J("org.crforge.core.battle.projectile.ProjectileEntity")
        self.Area = J("org.crforge.core.battle.unit.AreaEffectEntity")

    def raw(self, m, decks) -> dict:
        std = m.std
        b = std.getBattle()
        players = []
        for s in (0, 1):
            side = std.getMatch().side(s)
            slots = list(side.getHand().slots())
            q = side.getHand().queue()
            hand = [dict(hand_index=h, name=decks[s][slots[h]]) for h in range(4) if h < len(slots) and slots[h] >= 0]
            players.append(dict(side=s, elixir_exact=side.getElixir() / 10000.0, hand=hand,
                                next_deck_index=int(q.get(0)) if q.size() else None))
        ents, towers, effects = [], [], []
        for e in b.getHolder().entities():
            if isinstance(e, self.World):
                h = e.getHitPoints()
                hp, mhp = (int(h.getHitPoints()), int(h.getMaximum())) if h is not None else (-1, -1)
                name = e.getData().name()
                if isinstance(e, self.Tower):
                    towers.append(dict(side=int(e.side()), type="king" if e.getData().king() else "princess", x=int(e.x()),
                                       y=int(e.y()), hp=hp, max_hp=mhp, destroyed=hp <= 0))
                    continue
                dep = int(e.getView().getDeployCountdown()) if isinstance(e, self.Char) else 0
                base, form = split_form(name)
                ents.append(dict(side=int(e.side()), x=int(e.x()), y=int(e.y()), name=base, hp=hp, max_hp=mhp, card_id=0,
                                 kind=12 if dep > 0 else 0, entity_id=int(e.getId()),
                                 status_flags=16 if form == 2 else 8 if form == 1 else 0))
            elif isinstance(e, (self.Proj, self.Area)):
                effects.append(dict(side=int(e.side()), x=int(e.x()), y=int(e.y()), name=e.getData().name()))
        return dict(tick=int(b.getTick()), players=players, entities=ents, episode=dict(crown_towers=towers),
                    effects=effects)


def tensors(raw, seat, deck, history, engine_deck, fv):
    bs = oc.from_engine(raw, seat, deck, history=history, engine_deck=engine_deck, unmapped=set(), feature_version=fv)
    tok, mask, sc = oc.to_tokens(bs)
    return tok, mask, sc, oc.to_unit_forms(bs)


def pct(a, q):
    return float(np.percentile(np.asarray(a), q)) if a else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=16)
    ap.add_argument("--steps", type=int, default=400, help="decisions per env (all envs step together)")
    ap.add_argument("--warm-steps", type=int, default=300, help="steps before timing (JIT + name tables)")
    ap.add_argument("--p1-envs", type=int, default=4, help="envs P1 runs on (it keeps its own history)")
    ap.add_argument("--fv-time", type=int, default=6, help="from_engine feature_version timed as P2' (CLXIII is 6)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    start_jvm(1)
    CfSpeed = jpype.JClass("CfSpeed")
    tables = CfSpeed.load(str(CF / "crforge_cache/tables/16.402.22"))
    pairs = read_decks(CF / "decks.tsv")
    ours = our_decks(pairs)
    JStr, JInt = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
    decks = jpype.JArray(JStr)([JStr(d) for p in pairs for d in (p[0], p[2])])
    slots = jpype.JArray(JInt)([JInt(s) for p in pairs for s in (p[1], p[3])])
    maps = jpype.JArray(JInt)([JInt(m) for o in ours for m in (o[2], o[3])])
    n = a.envs
    r = CfSpeed.Rollout(tables, decks, slots, maps, n, 1, 10)
    r.javaPolicy = True
    r.buildObs = True
    dump = CfSpeed.Dump()
    p1 = JPypeReader()
    tok = np.frombuffer(memoryview(r.tokB), np.float32).reshape(n, 2, 64, 14)
    msk = np.frombuffer(memoryview(r.maskB), np.uint8).reshape(n, 2, 64)
    sc = np.frombuffer(memoryview(r.scB), np.float32).reshape(n, 2, 70)
    frm = np.frombuffer(memoryview(r.formB), np.int8).reshape(n, 2, 64)
    done = np.frombuffer(memoryview(r.doneB), np.uint8)

    hist2 = [[{}, {}] for _ in range(n)]
    hist1 = [[{}, {}] for _ in range(a.p1_envs)]
    hist6 = [[{}, {}] for _ in range(n)]
    tokF, scF = r.tokB.asFloatBuffer(), r.scB.asFloatBuffer()
    t = dict(java_step_env_us=[], p3_call_us=[], p2_dump_us=[], p2_raw_us=[], p2_tensors_fv4_us=[],
             p2_tensors_fvT_us=[], p1_reads_us=[], p1_tensors_fv4_us=[])
    cmp = dict(rows=0, rows_equal=0, tok_diff=0, mask_diff=0, sc_diff=0, form_diff=0, sc_hand_diff_seat1=0,
               first_diffs=[])
    names_resolved = 0
    for step in range(a.warm_steps + a.steps):
        w = time.perf_counter()
        r.step()
        java_us = (time.perf_counter() - w) * 1e6
        for i in np.flatnonzero(done):                    # a match ended: the env was reset, fresh histories
            hist2[i] = [{}, {}]
            hist6[i] = [{}, {}]
            if i < a.p1_envs:
                hist1[i] = [{}, {}]
        if r.names.missing.size():                        # new names: resolve, rebuild this step's Java obs
            names_resolved += resolve(r.names)
            r.observe()
        timed = step >= a.warm_steps
        rec = (lambda k, v: t[k].append(v)) if timed else (lambda k, v: None)
        rec("java_step_env_us", java_us / n)
        dnames = list(dump.names)
        for i in range(n):
            p = int(r.pairOf[i])
            eng = (pairs[p][0], pairs[p][2])
            m = r.m[i]
            c0 = time.thread_time()
            d = list(dump.dump(m))
            c1 = time.thread_time()
            if len(dnames) < dump.names.size():
                dnames = list(dump.names)
            raw = raw_from_dump(d, dnames, eng)
            c2 = time.thread_time()
            rec("p2_dump_us", (c1 - c0) * 1e6 / 2)
            rec("p2_raw_us", (c2 - c1) * 1e6 / 2)
            for seat in (0, 1):
                c3 = time.thread_time()
                pt, pm, ps, pf = tensors(raw, seat, ours[p][seat], hist2[i][seat], eng[seat], 4)
                c4 = time.thread_time()
                tensors(raw, seat, ours[p][seat], hist6[i][seat], eng[seat], a.fv_time)
                c5 = time.thread_time()
                rec("p2_tensors_fv4_us", (c4 - c3) * 1e6)
                rec("p2_tensors_fvT_us", (c5 - c4) * 1e6)
                # identity: the Java buffers vs the Python tensors
                jt, jm, js, jf = tok[i, seat], msk[i, seat].astype(bool), sc[i, seat], frm[i, seat]
                eq_tok, eq_m, eq_f = np.array_equal(jt, pt), np.array_equal(jm, pm), np.array_equal(jf, pf)
                eq_sc = np.array_equal(js, ps) if seat == 0 else (np.array_equal(js[:7], ps[:7])
                                                                  and np.array_equal(js[52:], ps[52:]))
                ok = eq_tok and eq_m and eq_sc and eq_f
                cmp["rows"] += 1
                cmp["rows_equal"] += int(ok)
                cmp["tok_diff"] += int(not eq_tok)
                cmp["mask_diff"] += int(not eq_m)
                cmp["sc_diff"] += int(not eq_sc)
                cmp["form_diff"] += int(not eq_f)
                if seat == 1 and not np.array_equal(js[7:52], ps[7:52]):
                    cmp["sc_hand_diff_seat1"] += 1
                if not ok and len(cmp["first_diffs"]) < 12:
                    bad = np.flatnonzero(~np.all(jt == pt, axis=1))[:3].tolist()
                    cmp["first_diffs"].append(dict(step=step, env=i, seat=seat, tok_rows=bad,
                                                   java=[jt[b].tolist() for b in bad], py=[pt[b].tolist() for b in bad],
                                                   sc_idx=np.flatnonzero(js != ps)[:6].tolist(),
                                                   n_tokens=[int(jm.sum()), int(pm.sum())]))
                if timed and i < 4:   # P3 through one JPype call (same state and tick: rebuilds identical rows)
                    off = i * 2 + seat
                    c6 = time.perf_counter()
                    m.obs(seat, r.names, tokF, off * 64 * 14, r.maskB, off * 64, scF, off * 70, r.formB, off * 64)
                    t["p3_call_us"].append((time.perf_counter() - c6) * 1e6)
            if i < a.p1_envs:
                c7 = time.thread_time()
                raw1 = p1.raw(m, eng)
                c8 = time.thread_time()
                for seat in (0, 1):
                    tensors(raw1, seat, ours[p][seat], hist1[i][seat], eng[seat], 4)
                rec("p1_reads_us", (c8 - c7) * 1e6 / 2)
                rec("p1_tensors_fv4_us", (time.thread_time() - c8) * 1e6 / 2)
    out = dict(envs=n, steps=a.steps, warm_steps=a.warm_steps, names_resolved=names_resolved,
               matches_done=int(r.matches.get()), plays_per_side=float(r.plays.get()) / max(1, 2 * int(r.matches.get())),
               unmapped_units=sorted(k for k, v in dict(r.names.unit).items() if v < 0),
               spells_mapped=sorted(k for k, v in dict(r.names.spell).items() if v >= 0),
               identity=cmp,
               us_per_seat_row={k: dict(n=len(v), mean=float(np.mean(v)) if v else None, p50=pct(v, 50), p90=pct(v, 90))
                                for k, v in t.items()})
    out["fv_time"] = a.fv_time
    out["note"] = ("per seat-row except java_step_env_us (one env decision on 1 Java thread: 10 ticks + both seats' P3 "
                   "obs). P2 = p2_dump_us (Java dump + JPype + list) + p2_raw_us (raw dict) + p2_tensors_fv4_us "
                   "(from_engine fv4 + to_tokens + to_unit_forms); p2_tensors_fvT_us = the same at fv_time. "
                   "P1 = p1_reads_us (JPype per-field) + p1_tensors_fv4_us. p3_call_us = CfSpeed.Match.obs via one "
                   "JPype call (wall). Times are thread CPU (time.thread_time) except the two *_call/step wall ones.")
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("identity", "us_per_seat_row")}, indent=1)[:4000])


if __name__ == "__main__":
    main()
