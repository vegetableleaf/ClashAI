"""Phase-3 reader validation (attack target + attack phase): checks V1-V10 of L74/parity/READER_PHASE3.md.

    python scratchpad/gauntlet/L74/parity/reader_val/validate_p3.py P3_FRAMES [FRAME_LOG] [--tables CSV_LOGIC_DIR]
           [--sim-cards CARDS_JSON]

Reads ALREADY-DECODED JSON only: the phase-3 capture (A: game_tick, entities, projectiles, effects,
phase2.units name/side/buffs, phase3 bodies/defs, read_us) and, optionally, the matching live_play --log-frames log
(B: tick -> t_dev and the recording segments, only to print video times). Bodies are keyed by generation id;
runtime addresses are only an in-frame join key and are never printed. One game tick = 50 ms of attack progress.
Prints one PASS / FAIL / SKIP line per check with its numbers, then per-attacker detail.

Two predictions are printed side by side where they differ: the SIM's measured attack cycle (royalesim 0.1.35
calibration combat.ATTACK_CYCLE = progress_credit: a fresh cycle is credited LoadTime, +50 a tick, the hit lands on
the tick progress reaches a multiple of HitSpeed, so the first hit comes (HitSpeed - LoadTime) / 50 - 1 ticks after
the entry frame) and the static-analysis guess of the private notes (hit at phase LoadTime). The capture decides.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
TABLES = REPO / "scratchpad/gauntlet/L74/apktables/out/device_builds/20261012T221627332682Z-50188/tables/csv_logic"
# The card table royalesim 0.1.35 (runtime 20261016-linux, RoyaleSim pin 4fd4d54) compiles in under
# cards.CARD_TABLE = client160402017_20261006 (card.rs EMBEDDED_CARDS_160402017_JSON); same bytes as this checkout's file.
SIM_CARDS = REPO / "research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json"
SIM_CARDS_SHA256 = "babaa3d129e370c5838f12001683e2a5579dbaec581fd94968e689aacfc3fb60"
# device-table timings the session must reproduce exactly: name -> (HitSpeed, LoadTime or None = not checked)
REQUIRED = {"Knight": (1200, 700), "Tesla": (1100, 700), "Xbow": (400, None), "PrincessTower": (800, None),
            "KingTower": (1000, 500)}
BASE_STEP = 50                 # progress per tick, unbuffed
P2_READ_US = (404, 1001)       # phase-2 read_us median / p95 over the 4 earlier captures (cost baseline)
SIM_FIELDS = (("HitSpeed", "hit_speed_ms"), ("LoadTime", "load_time_ms"), ("LoadFirstHit", "load_first_hit"),
              ("Range", "range_milli"), ("MinimumRange", "minimum_range_milli"), ("SightRange", "sight_range_milli"))
SIM_GATED = ("HitSpeed", "LoadTime", "LoadFirstHit")


class F:
    """One valid phase-3 frame, keyed by generation id."""

    def __init__(self, j):
        self.tick, self.read_us = j["game_tick"], j.get("read_us")
        addr = {e["address"]: e["category"] for e in j["entities"]}
        self.ents = {e["category"]: e for e in j["entities"]}
        self.name = {u["generation"]: u["name"] for u in j["phase2"]["units"]}
        self.side = {u["generation"]: u["side"] for u in j["phase2"]["units"]}
        self.buffs = {u["generation"]: u["buffs"] for u in j["phase2"]["units"]}
        self.att = {b["generation"]: b["attack"] for b in j["phase3"]["bodies"]}
        self.why = {b["generation"]: b.get("null_reason") for b in j["phase3"]["bodies"]}
        self.defid = {b["generation"]: b["definition_id"] for b in j["phase3"]["bodies"]}
        self.proj = {p["generation_key"]: (addr.get(p["source"]), addr.get(p["target"])) for p in j.get("projectiles", [])}
        self.fx_sides = {e["side"] for e in j.get("effects", [])}
        self.defs = j["phase3"]["defs"]


def load(path):
    rows = [json.loads(s) for s in open(path, encoding="utf-8") if s.strip()]
    active = [r for r in rows if r.get("battle_active") and r.get("phase3")]
    return [F(r) for r in active if r["phase3"]["valid"]], len(active)


def table_timings(root):
    """Device tables: Name -> {HitSpeed, LoadTime} (first definition of a Name wins)."""
    out, root = {}, Path(root)
    if not root.is_dir():
        return out
    for p in sorted(root.glob("characters/**/*.toml")) + [root / "buildings.toml"]:
        if not p.is_file():
            continue
        for sec in re.split(r"(?m)^\[", p.read_text(encoding="utf-8", errors="ignore")):
            kv = dict(re.findall(r"(?m)^(Name|HitSpeed|LoadTime)\s*=\s*\"?([^\"\n]+)\"?\s*$", sec))
            name = kv.pop("Name", None) or (sec.split("]", 1)[0].split(".")[-1] if "]" in sec else None)
            if name and kv and name not in out:
                out[name] = {k: int(v) for k, v in kv.items() if v.lstrip("-").isdigit()}
    return out


def sim_cards(path):
    """SIM card table: name -> row with hit_speed_ms / load_time_ms / ... (units first, then cards/towers/evos/heroes)."""
    path = Path(path)
    if not path.is_file():
        return {}, None
    raw = path.read_bytes()
    d = json.loads(raw)
    rows = {}
    for key, u in (d.get("units") or {}).items():
        rows.setdefault(u.get("name", key), u)
    for group in ("cards", "towers", "evolutions", "hero_forms"):
        for u in d.get(group) or []:
            if isinstance(u, dict) and "name" in u:
                rows.setdefault(u["name"], u)
    return rows, hashlib.sha256(raw).hexdigest()


def sim_row(rows, name):
    if name in rows:
        return rows[name]
    if name.endswith("Hero"):            # memory KnightHero -> SIM Knight_hero
        return rows.get(name[:-4] + "_hero")
    return None


def sim_first_hit_ticks(row):
    """SIM progress_credit: first hit (HitSpeed - LoadTime) / 50 - 1 ticks after the entry frame, when the load timer
    had run out and LoadTime <= HitSpeed; None when the SIM rule depends on more (LoadFirstHit, LoadTime > HitSpeed)."""
    if not row or not row.get("hit_speed_ms"):
        return None
    hs, lt = row["hit_speed_ms"], row.get("load_time_ms") or 0
    if row.get("load_first_hit") or lt > hs:
        return None
    return (hs - lt) // BASE_STEP - 1


def step_law(buffs):
    """Expected progress per tick under the body's buffs (HitSpeedMultiplier: >100 speeds up, <0 slows)."""
    m = [b["config"]["HitSpeedMultiplier"] for b in buffs or [] if b["config"]["HitSpeedMultiplier"]]
    s = BASE_STEP * max([100] + [v for v in m if v > 0]) // 100
    return max(0, s * (100 - max([0] + [-v for v in m if v < 0])) // 100)


def buff_key(buffs):
    return tuple(sorted((b["name"], b["config"]["HitSpeedMultiplier"]) for b in buffs or []))


def no_refresh(b0, b1):
    """Same buffs in both samples and none re-applied in between (every remaining timer went down)."""
    if buff_key(b0) != buff_key(b1):
        return False
    r0 = sorted((b["name"], b["remaining_ms_raw"]) for b in b0 or [])
    r1 = sorted((b["name"], b["remaining_ms_raw"]) for b in b1 or [])
    return all(y[1] < x[1] or x[1] == -1 for x, y in zip(r0, r1))


def intervals(frames):
    for f0, f1 in zip(frames, frames[1:]):
        if f1.tick > f0.tick:
            yield f0, f1, f1.tick - f0.tick


def linear(f0, f1, dt, g):
    """(progress at f0, step) when g kept one target and progressed at a constant integer step, else None."""
    a0, a1 = f0.att.get(g), f1.att.get(g)
    if not a0 or not a1 or a0["target_gen"] in (None, "unlisted") or a0["target_gen"] != a1["target_gen"]:
        return None
    if a0["seq_idx"] != -1 or a1["seq_idx"] != -1 or a0["progress_raw"] <= 0:
        return None
    d = a1["progress_raw"] - a0["progress_raw"]
    if d <= 0 or d % dt:
        return None
    return a0["progress_raw"], d // dt


def candidates(p0, step, dt, hs):
    """Phases (progress mod HitSpeed, after the tick's step) the attacker passed through during the interval."""
    return {(p0 + step * k) % hs for k in range(1, dt + 1)}


def fixed_phase(events):
    """events = [candidate sets] -> (phase, support count) of the phase present in the most events."""
    c = collections.Counter(x for e in events for x in e)
    return c.most_common(1)[0] if c else (None, 0)


def video_clock(blog):
    if not blog:
        return lambda t: "no video"
    ev = [json.loads(s) for s in open(blog, encoding="utf-8") if s.strip()]
    tdev = {e["tick"]: e["t_dev"] for e in ev if e.get("event") == "frame"}
    segs = next((e["segments"] for e in ev if e.get("event") == "recording"), [])
    ks = sorted(tdev)
    if not segs or not ks:
        return lambda t: "no video"

    def V(t):
        td = tdev.get(t) or tdev[min(ks, key=lambda k: abs(k - t))]
        i = max((k for k, (_, t0) in enumerate(segs) if t0 <= td), default=0)
        s = td - segs[i][1]
        return f"seg{i} {int(s // 60)}:{s % 60:05.2f}"
    return V


def verdict(ok, enough=True):
    return ("PASS" if ok else "FAIL") if enough else "SKIP"


def run(frames, n_active, blog=None, tables=TABLES, sim_path=SIM_CARDS):
    out, V = [], video_clock(blog)
    if not frames:
        return ["NO VALID PHASE-3 FRAMES"]
    name = {}
    for f in frames:
        name.update(f.name)
    defs, def_of = {}, {}
    for f in frames:
        for d in f.defs:
            defs.setdefault(d["definition_id"], d)
        def_of.update(f.defid)
    hs_of = {g: defs[d]["HitSpeed"] for g, d in def_of.items() if d in defs and defs[d]["HitSpeed"] > 0}
    by_name = {d["name"]: d for d in defs.values()}

    # V1 definition timings vs the device tables
    req = {n: (by_name[n]["HitSpeed"], by_name[n]["LoadTime"]) for n in REQUIRED if n in by_name}
    req_bad = [n for n, (h, lt) in req.items() if h != REQUIRED[n][0] or (REQUIRED[n][1] is not None and lt != REQUIRED[n][1])]
    tab = table_timings(tables)
    tab_bad = [(d["name"], k, d[k], tab[d["name"]][k]) for d in defs.values() if d["name"] in tab
               for k in ("HitSpeed", "LoadTime") if k in tab[d["name"]] and d[k] != tab[d["name"]][k]]
    towers = all(n in by_name for n in ("PrincessTower", "KingTower"))
    out.append(f"V1 {verdict(not req_bad and not tab_bad and towers)} definitions={len(defs)} required_seen={req} "
               f"required_mismatch={req_bad} towers_seen={towers} table_names_compared="
               f"{sum(d['name'] in tab for d in defs.values())} table_mismatch={tab_bad}")

    # V2 shooter target == projectile target at the projectile's first sample
    seen, v2, launches, prev = set(), collections.Counter(), [], None
    for f in frames:
        for key, (src, tgt) in f.proj.items():
            if key in seen:
                continue
            seen.add(key)
            if prev is not None and src is not None:
                launches.append((src, tgt, prev, f))
            a = f.att.get(src)
            if not a or tgt is None:
                continue
            kind = "tower" if name.get(src, "").endswith("Tower") else "other"
            v2[kind, a["target_gen"] == tgt] += 1
            v2["either", a["target_gen"] == tgt or bool(prev and (prev.att.get(src) or {}).get("target_gen") == tgt)] += 1
        prev = f
    n2 = sum(v2[k, b] for k in ("tower", "other") for b in (True, False))
    r2 = (v2["tower", True] + v2["other", True]) / n2 if n2 else 0
    out.append(f"V2 {verdict(r2 >= 0.95, n2 >= 10)} n={n2} match={r2:.3f} (need >= 0.95) towers "
               f"{v2['tower', True]}/{v2['tower', True] + v2['tower', False]} others "
               f"{v2['other', True]}/{v2['other', True] + v2['other', False]}; shooter target at either "
               f"bracketing sample {v2['either', True]}/{n2}")

    # attack-instant events: projectile launches (shooters) and clean hp drops of the target (non-shooters)
    shooters = {g for g, *_ in launches}
    events, ev_ticks = collections.defaultdict(list), collections.defaultdict(list)

    def clean_drop(f0, f1, g, v):
        """v lost hp between f0 and f1 and only g can have done it (no other attacker, shot or spell from g's side)."""
        e0, e1 = f0.ents.get(v), f1.ents.get(v)
        if not e0 or not e1 or e1["hp"] >= e0["hp"]:
            return None
        others = any(h != g and a and a["target_gen"] == v for f in (f0, f1) for h, a in f.att.items())
        shot = any(t == v for f in (f0, f1) for _, t in f.proj.values())
        spell = f0.side.get(g) in f0.fx_sides | f1.fx_sides
        return not (others or shot or spell)

    for g, _, f0, f1 in launches:
        lin = linear(f0, f1, f1.tick - f0.tick, g)
        if lin and g in hs_of:
            events[name.get(g)].append(candidates(lin[0], lin[1], f1.tick - f0.tick, hs_of[g]))
            ev_ticks[name.get(g)].append(f1.tick)
    step_ok = collections.Counter()
    for f0, f1, dt in intervals(frames):
        for g in f1.att:
            lin = linear(f0, f1, dt, g)
            if not lin:
                continue
            if not f0.buffs.get(g) and not f1.buffs.get(g):
                step_ok[name.get(g), lin[1] == BASE_STEP] += 1
            if g in shooters or g not in hs_of:
                continue
            if clean_drop(f0, f1, g, f0.att[g]["target_gen"]):
                events[name.get(g)].append(candidates(lin[0], lin[1], dt, hs_of[g]))
                ev_ticks[name.get(g)].append(f1.tick)
    phase = {n: (fixed_phase(e), len(e)) for n, e in events.items()}

    def phase_line(tag, unit, extra=""):
        (ph, sup), n = phase.get(unit, ((None, 0), 0))
        ok = n >= 5 and sup / max(n, 1) >= 0.9
        so = step_ok[unit, True], step_ok[unit, True] + step_ok[unit, False]
        law = so[1] == 0 or so[0] / so[1] >= 0.9
        first = ", ".join(f"t{t} ({V(t)})" for t in ev_ticks.get(unit, [])[:3])
        return (f"{tag} {verdict(ok and law, n >= 5)} {unit}: events={n} fixed_phase={ph} support={sup}/{n} "
                f"(need >= 5 events, >= 90%){extra}; unbuffed step=+{BASE_STEP}/tick in {so[0]}/{so[1]} "
                f"same-target intervals; first events {first}")

    lt_k = by_name.get("Knight", {}).get("LoadTime")
    out.append(phase_line("V3", "Knight", f"; predictions: SIM progress_credit 0, notes {lt_k}"))

    # V4 retargets (Tesla): previous target = old target; progress reported (notes: reset; SIM: kept when the new
    # target is already in reach, combat.RETARGET_PROGRESS = keep_when_dead_or_in_reach)
    def retargets(units):
        c, rows = collections.Counter(), []
        for f0, f1, dt in intervals(frames):
            for g, a1 in f1.att.items():
                a0 = f0.att.get(g)
                if name.get(g) not in units or not a0 or not a1:
                    continue
                x, y = a0["target_gen"], a1["target_gen"]
                if x in (None, "unlisted") or y in (None, "unlisted", x):
                    continue
                alive = x in f1.ents
                c["n"] += 1
                c["prev_ok"] += a1["prev_target_gen"] == x if alive else a1["prev_target_gen"] in (None, "unlisted", x)
                c["reset"] += 0 <= a1["progress_raw"] <= step_law(f1.buffs.get(g)) * dt
                c["switch" if alive else "kill"] += 1
                rows.append(f"t{f1.tick} ({V(f1.tick)}) {x}->{y} prev={a1['prev_target_gen']} progress "
                            f"{a0['progress_raw']}->{a1['progress_raw']}")
        return c, rows
    c4, rows4 = retargets({"Tesla", "Tesla_EV1"})
    n4 = c4["n"]
    out.append(f"V4 {verdict(n4 and c4['prev_ok'] / n4 >= 0.9, n4 >= 2)} Tesla retargets={n4} (switch {c4['switch']}, "
               f"after kill {c4['kill']}) previous==old {c4['prev_ok']}/{n4} (need >= 90%); progress reset "
               f"{c4['reset']}/{n4} [notes predict reset; SIM keeps it on an in-reach switch]; first {rows4[:3]}")

    c5, _ = retargets({"Xbow", "Xbow_EV1"})
    out.append(phase_line("V5", "Xbow", f"; retarget resets {c5['reset']}/{c5['n']}"))

    # V6 buffed step law: frozen -> 0, Hero IW slow (-30) -> 35, between refreshes
    c6 = collections.Counter()
    for f0, f1, dt in intervals(frames):
        for g, a1 in f1.att.items():
            a0, b0, b1 = f0.att.get(g), f0.buffs.get(g), f1.buffs.get(g)
            if not a0 or not a1 or not b1 or a0["target_gen"] != a1["target_gen"] or a0["target_gen"] is None:
                continue
            if a0["seq_idx"] != -1 or a0["progress_raw"] <= 0 or not no_refresh(b0, b1):
                continue
            want = step_law(b1)
            if want == BASE_STEP:
                continue
            kind = "frozen" if want == 0 else ("slow35" if want == 35 else f"step{want}")
            c6[kind, "n"] += 1
            c6[kind, "ok"] += a1["progress_raw"] - a0["progress_raw"] == want * dt
    kinds = sorted({k for k, _ in c6})
    ok6 = c6["frozen", "n"] >= 3 and c6["slow35", "n"] >= 3 and all(c6[k, "ok"] == c6[k, "n"] for k in ("frozen", "slow35"))
    out.append(f"V6 {verdict(ok6, c6['frozen', 'n'] + c6['slow35', 'n'] > 0)} "
               + " ".join(f"{k}: {c6[k, 'ok']}/{c6[k, 'n']} exact" for k in kinds)
               + " (need frozen and slow35 each >= 3 intervals, all exact)")

    # V7 taunt: own bodies switch to an opponent Hero Knight on the same sample their projectiles do
    hks = {g for g, n in name.items() if n == "KnightHero"}
    rows7, ok7 = [], 0
    for hk in hks:
        for g in sorted({g for f in frames for g, a in f.att.items() if a and a["target_gen"] == hk}):
            ta = next(f.tick for f in frames if (f.att.get(g) or {}).get("target_gen") == hk)
            tp = next((f.tick for f in frames if (g, hk) in f.proj.values()), None)
            if tp is None:
                continue
            ok7 += abs(tp - ta) <= 3
            rows7.append(f"{name.get(g)}: body t{ta} proj t{tp} ({V(ta)})")
    out.append(f"V7 {verdict(bool(rows7) and ok7 == len(rows7), bool(rows7))} hero_knights={len(hks)} "
               f"shooters={len(rows7)} same-sample (<= 1 frame) {ok7}/{len(rows7)}; {rows7[:4]}")

    # V8 target sanity + null census + cost
    t, why = collections.Counter(), collections.Counter()
    for f in frames:
        for g, a in f.att.items():
            if a is None:
                why[f.why.get(g), name.get(g)] += 1
                continue
            for k in ("target_gen", "prev_target_gen"):
                v = a[k]
                t[k, "null" if v is None else ("unlisted" if v == "unlisted" else "listed")] += 1
    rows8 = sum(t["target_gen", s] for s in ("null", "listed", "unlisted"))
    r8 = (t["target_gen", "null"] + t["target_gen", "listed"]) / rows8 if rows8 else 0
    ru = sorted(f.read_us for f in frames if f.read_us is not None)
    med, p95 = (st.median(ru), ru[int(0.95 * (len(ru) - 1))]) if ru else (None, None)
    bad = sum(n for (w, _), n in why.items() if w in ("vtable", "owner", "read"))
    out.append(f"V8 {verdict(r8 >= 0.99, rows8 > 0)} target null/listed {r8:.4f} of {rows8} rows (need >= 0.99; "
               f"unlisted {t['target_gen', 'unlisted']}, prev unlisted {t['prev_target_gen', 'unlisted']}); "
               f"valid frames {len(frames)}/{n_active}; vtable/owner/read nulls {bad}; read_us median {med} p95 {p95} "
               f"(phase-2 baseline {P2_READ_US[0]} / {P2_READ_US[1]})")

    # V9 every observed definition vs the SIM's card table (runtime 20261016-linux)
    srows, ssha = sim_cards(sim_path)
    mism, missing = [], []
    for d in sorted(defs.values(), key=lambda d: d["name"]):
        r = sim_row(srows, d["name"])
        if r is None:
            missing.append(d["name"])
            continue
        for mk, sk in SIM_FIELDS:
            mv, sv = d.get(mk), r.get(sk)
            sv = int(bool(sv)) if mk == "LoadFirstHit" else (0 if sv is None and mk == "MinimumRange" else sv)
            if mv is not None and sv is not None and mv != sv:
                mism.append((d["name"], mk, mv, sv))
    gated = [m for m in mism if m[1] in SIM_GATED]
    tag = "the 0.1.35 table" if ssha == SIM_CARDS_SHA256 else f"NOT the 0.1.35 table (sha {str(ssha)[:12]})"
    out.append(f"V9 {verdict(not gated, bool(srows))} memory vs SIM cards ({tag}): definitions {len(defs)}, "
               f"compared {len(defs) - len(missing)}, timing mismatches {len(gated)} {gated}; range mismatches "
               f"{[m for m in mism if m not in gated]}; not in SIM table {missing}")
    extra = [(d["name"], d.get("ActivationTime"), d.get("AttackDashTime")) for d in defs.values()
             if d.get("ActivationTime") or d.get("AttackDashTime")]
    out.append(f"   definitions with ActivationTime / AttackDashTime set (not in the SIM table): {extra}")

    # V10 first hit on a fresh target: entry frame (progress 0 -> > 0 on a new target, load timer run out) to the
    # first attack instant (shooter: projectile launch; melee: the target's hp drop), vs the SIM prediction
    first = collections.defaultdict(collections.Counter)
    rows10 = []
    gens = sorted({g for f in frames for g, a in f.att.items() if a})
    launch_at = collections.defaultdict(list)          # g -> [(f0, f1)] of its projectile launches
    for g, _, f0, f1 in launches:
        launch_at[g].append((f0, f1))
    for g in gens:
        nm = name.get(g)
        srow = sim_row(srows, nm)
        pred = sim_first_hit_ticks(srow)
        series = [f for f in frames if g in f.att]
        for k in range(1, len(series)):
            f0, f1 = series[k - 1], series[k]
            a0, a1 = f0.att[g], f1.att[g]
            if not a1 or a1["target_gen"] in (None, "unlisted") or a1["progress_raw"] <= 0 or f1.tick <= f0.tick:
                continue
            v = a1["target_gen"]
            if a0 and a0["progress_raw"] > 0:
                continue                     # a running or kept swing (in-reach switch) is not a fresh cycle
            if a0 and a0["load_raw"] > 0:
                first[nm]["reentry_load_running"] += 1
                continue
            acq = next((s.tick for s in reversed(series[:k]) if not s.att[g] or s.att[g]["target_gen"] != v), None)
            hit, conf, j = None, False, k
            while j + 1 < len(series) and series[j + 1].att[g] and series[j + 1].att[g]["target_gen"] == v:
                h0, h1 = series[j], series[j + 1]
                if g in shooters:
                    if any(x[0] is h0 and x[1] is h1 for x in launch_at[g]):
                        hit = (h0.tick + 1, h1.tick)
                else:
                    c = clean_drop(h0, h1, g, v)
                    if c is not None:
                        hit, conf = (h0.tick + 1, h1.tick), not c
                if hit:
                    break
                j += 1
            if not hit:
                first[nm]["interrupted"] += 1
                continue
            if conf:
                first[nm]["confounded"] += 1
                continue
            # model-free: entry in [f0+1, f1], attack instant in [hit0, hit1] -> delay bracket (2-5 ticks wide)
            lo, hi = hit[0] - f1.tick, hit[1] - (f0.tick + 1)
            p1, dt = a1["progress_raw"], f1.tick - f0.tick
            first[nm]["n"] += 1
            if pred is not None:
                # the SIM delay split in two parts the capture pins down sharply:
                # (a) entry credit: progress on the entry frame = LoadTime + 50 -> p1 = LoadTime + 50 + 50 x (ticks
                #     since entry), those ticks in [0, dt - 1];
                # (b) the hit: on the tick progress reaches the next HitSpeed multiple -> f1 + (m - p1) / 50 must
                #     fall inside the observed launch / hp-drop bracket (width = one sample gap).
                hs, lt = srow["hit_speed_ms"], srow.get("load_time_ms") or 0
                since, rem = divmod(p1 - lt - BASE_STEP, BASE_STEP)
                credit_ok = rem == 0 and 0 <= since < dt
                sim_hit = f1.tick + (-(-p1 // hs) * hs - p1) // BASE_STEP
                hit_ok = hit[0] <= sim_hit <= hit[1]
                first[nm]["with_pred"] += 1
                first[nm]["credit_ok"] += credit_ok
                first[nm]["hit_ok"] += hit_ok
                first[nm]["both_ok"] += credit_ok and hit_ok
                first[nm]["bracket_ok"] += lo <= pred <= hi
            acq_s = f" target-set->hit <= {hit[1] - acq - 1}" if acq is not None else ""
            rows10.append(f"{nm} t{f1.tick} ({V(f1.tick)}) entry->hit [{lo}, {hi}] SIM {pred} progress@entry-sample "
                          f"{p1} hit t{hit[0]}..t{hit[1]}{acq_s}")
    n10 = sum(c["with_pred"] for c in first.values())
    in10 = sum(c["both_ok"] for c in first.values())
    out.append(f"V10 {verdict(n10 and in10 / n10 >= 0.9, n10 >= 5)} first hit on a fresh target vs SIM "
               f"(HitSpeed - LoadTime) / 50 - 1: entry credit AND hit tick as SIM {in10}/{n10} (need >= 5, >= 90%); "
               "per unit " + "; ".join(
                   f"{n}: SIM {sim_first_hit_ticks(sim_row(srows, n))} ticks, credit LoadTime+50 {c['credit_ok']}/"
                   f"{c['with_pred']}, hit at next HitSpeed multiple {c['hit_ok']}/{c['with_pred']}, SIM delay in the "
                   f"model-free bracket {c['bracket_ok']}/{c['with_pred']} (measured {c['n']}, interrupted "
                   f"{c['interrupted']}, confounded {c['confounded']}, reentry {c['reentry_load_running']})"
                   for n, c in sorted(first.items()) if c["n"] or c["interrupted"]))
    out.append(f"   V10 rows (first 10): {rows10[:10]}")

    out.append("-- per attacker: fixed hit phase (events, support), HitSpeed/LoadTime")
    for n, ((ph, sup), k) in sorted(phase.items(), key=lambda x: -x[1][1]):
        d = by_name.get(n, {})
        out.append(f"   {n}: phase {ph} support {sup}/{k}  HitSpeed {d.get('HitSpeed')} LoadTime {d.get('LoadTime')}")
    out.append("-- null attack reasons (reason, unit): " + str(why.most_common(12)))
    out.append(f"-- V4 retarget rows (first 8): {rows4[:8]}")
    return out


def main(argv):
    opts = {"--tables": TABLES, "--sim-cards": SIM_CARDS}
    for k in list(opts):
        if k in argv:
            i = argv.index(k)
            opts[k], argv = argv[i + 1], argv[:i] + argv[i + 2:]
    frames, n_active = load(argv[0])
    for line in run(frames, n_active, argv[1] if len(argv) > 1 else None, opts["--tables"], opts["--sim-cards"]):
        print(line)


if __name__ == "__main__":
    main(sys.argv[1:])
