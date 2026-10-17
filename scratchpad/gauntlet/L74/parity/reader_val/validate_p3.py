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

Attack instants (V3/V5 phase, V10 first hit): projectile launches for shooters; for other units with LoadTime > 0 the
load-timer re-arm (exact fire tick); clean target hp drops only for the rest. A phase is "hit" on the tick that CROSSES
it (`candidates`): the counter carries the overshoot under a slow (ATTACK_PHASE_1016.md).
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
        # phase 3b (READER_PHASE3B.md): remaining deploy ms per body; absent in older captures -> V11 SKIP
        self.dep = {b["generation"]: b["deploy_remaining_raw"] for b in j["phase3"]["bodies"] if "deploy_remaining_raw" in b}
        self.beh = {e["category"]: e.get("behavior_state_raw") for e in j["entities"]}
        self.stick = {b["generation"]: b["deploy_tick_raw"] for b in j["phase3"]["bodies"] if "deploy_tick_raw" in b}
        self.ctick = {b["generation"]: b["card_tick_raw"] for b in j["phase3"]["bodies"] if "card_tick_raw" in b}
        self.act = {b["generation"]: b["active_ms_raw"] for b in j["phase3"]["bodies"] if "active_ms_raw" in b}
        # phase 3c (READER_PHASE3C.md): the whole body row, for the hidden-state fields; V12 SKIPs without them
        self.row3c = {b["generation"]: b for b in j["phase3"]["bodies"] if "shield_hp_raw" in b}


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


RESET_WINDOW = 10   # ticks after a stun / freeze ends in which a re-scan may still land (the resume rescan is immediate)


def is_reset_buff(b):
    """A buff that resets targeting: a full stop (HitSpeedMultiplier -100: Freeze, Zap, Ice Spirit, Hero IW freeze)
    or a stun / freeze / taunt by name."""
    return b["config"]["HitSpeedMultiplier"] <= -100 or bool(re.search(r"stun|freeze|taunt|zap", b["name"], re.I))


def troop_in_range(f, g, rng):
    """Is an enemy non-tower body within the attacker's Range (centre distance; edges and radii not added)?"""
    e = f.ents.get(g)
    if not e or not rng or "x" not in e:
        return False
    return any(o["side"] != e["side"] and not f.name.get(h, "").endswith("Tower") and "x" in o
               and (o["x"] - e["x"]) ** 2 + (o["y"] - e["y"]) ** 2 <= rng * rng for h, o in f.ents.items())


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
    if a0["seq_idx"] not in (-1, 0) or a1["seq_idx"] not in (-1, 0) or a0["progress_raw"] <= 0:
        return None
    d = a1["progress_raw"] - a0["progress_raw"]
    if d <= 0 or d % dt:
        return None
    return a0["progress_raw"], d // dt


def candidates(p0, step, dt, hs, ks=None):
    """Hit phases the attacker CROSSED during the interval (ticks ks, default 1..dt after f0): every multiple of
    BASE_STEP in (progress - step, progress] of a tick, mod HitSpeed. The counter is never reset or snapped by a hit, so
    under a slow (35/tick) a hit lands on the tick that passes the phase and the overshoot carries into the next cycle
    (live 1016: Knight 1190 -> 1225 -> ... 2415 -> 3605, every load re-arm on the crossing tick; SIM combat.rs fires on
    progress / HitSpeed growing). At +50 on the 50-grid this is exactly {progress mod HitSpeed}."""
    out = set()
    for k in ks or range(1, dt + 1):
        x = p0 + step * k
        out.update(m % hs for m in range(x // BASE_STEP * BASE_STEP, x - step, -BASE_STEP))
    return out


def rearm(f0, f1, g, lt):
    """The attacker fired in (f0, f1]: its load timer ROSE (a fire re-arms it to LoadTime, then -50 a tick; a sample pair
    whose tick gap over-reports the game advance -- 1016 t2700->2702, progress +50, load -50 -- only slows the fall).
    -> (lo, hi) fire-tick bracket: (t, t) when LoadTime - load is a whole number of ticks inside the interval, else
    (f0.tick + 1, f1.tick); None when it did not fire. Only for LoadTime > 0 (a LoadTime-0 unit's timer never moves)."""
    a0, a1 = f0.att.get(g), f1.att.get(g)
    dt = f1.tick - f0.tick
    if lt <= 0 or not a0 or not a1 or a1["load_raw"] <= a0["load_raw"]:
        return None
    back, r = divmod(lt - a1["load_raw"], BASE_STEP)
    return (f1.tick - back,) * 2 if not r and 0 <= back < dt else (f0.tick + 1, f1.tick)


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


# Phase 3b (READER_PHASE3B.md). Frame-tick convention (measured 10-17 live smoke): a body created while the battle tick
# reads X is first visible in the frame labelled X + 1, so its creation frame tick is deploy_tick_raw + 1 while it is
# still deploying (card_tick_raw + 1 for a card-made object without a deploy; first - active_ms_raw / 50 for a
# never-deploying child, whose active time is 0 on its creation frame). The countdown alone gives the same tick for
# card-played troops only: they take their first -50 step on the creation tick (credit 1), while the Hero Ice Wizard,
# its cube and other late-created bodies take it one tick later (credit 0).
COUNTDOWN_CREDIT = 1


def countdown_creation(first_tick, remaining, deploy_time, credit=COUNTDOWN_CREDIT):
    """Creation frame tick from the countdown alone (pre-tick-field captures): (DeployTime - remaining) / 50 steps ran
    by the frame. None when the countdown does not read back to a DeployTime start (no timer, other start, off grid)."""
    if not deploy_time or not remaining or remaining > deploy_time or (deploy_time - remaining) % BASE_STEP:
        return None
    return first_tick - (deploy_time - remaining) // BASE_STEP + credit


def creation_tick(first_tick, remaining, deploy_tick, card_tick, active=None, behaviour=None):
    """Creation frame tick of a body at its FIRST sighting (frame first_tick) -> (tick, source) or (None, reason).
    Still deploying: its deploy stamp; else a card-made object's card tick (diggers, the drill dig, a staggered recruit);
    else a never-deploying child's active time (0 on its creation frame, +50 a tick); a body in its stagger (11) or
    without any of these: None."""
    if remaining is None:
        return None, "null"
    if remaining > 0 and deploy_tick and deploy_tick > 0:
        return deploy_tick + 1, "deploy_tick"
    if card_tick is not None and card_tick >= 0:
        return card_tick + 1, "card_tick"
    if behaviour == 11:
        return None, "stagger"
    if remaining == 0 and active is not None and active >= 0 and active % BASE_STEP == 0:
        return first_tick - active // BASE_STEP, "active_ms"
    return None, "no_tick"


def deploy_lines(frames, defs, def_of, name):
    """V11 (phase 3b): (a) every new body's creation tick inside its first-sighting gap (prev frame, first], from the
    tick fields (or the countdown alone in a capture without them); (b) a card-made body's countdown started at
    DeployTime on that tick, never later (a longer start carried by a spell, e.g. Goblin Barrel goblins, is listed
    apart; a too-early tick already fails (a)); (c) -50 a tick while deploying (definitions not speed-scaled), zero
    reached inside the gap; (d) behaviour
    4 <=> countdown > 0; (e) the deploy stamp is constant for a body's life and changes only when a new deploy
    starts (entry into behaviour 4), inside that gap."""
    if not any(f.dep for f in frames):
        return ["V11 SKIP no deploy_remaining_raw in this capture (pre-3b probe)"]
    ticks = any(f.stick for f in frames)
    dt_of = {g: defs[d].get("DeployTime") for g, d in def_of.items() if d in defs}
    scaled = {g for g, d in def_of.items() if d in defs and defs[d].get("DeployTimeAffectedByCharacterSpeed")}
    c, per, src = collections.Counter(), collections.defaultdict(collections.Counter), collections.Counter()
    starts, bad_rows, credit = collections.defaultdict(collections.Counter), collections.Counter(), collections.Counter()
    kids, longer = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    kids_act = collections.Counter()
    seen, prev = set(), None
    for f in frames:
        for g, r in f.dep.items():
            c["rows"] += 1
            if r is None:
                c["null_rows"] += 1
                continue
            b = f.beh.get(g)
            if b is not None:
                c["state_rows"] += 1
                if (b == 4) == (r > 0):
                    c["state_ok"] += 1
                else:
                    bad_rows[name.get(g), b, r > 0] += 1
            if g in seen or prev is None:
                continue
            seen.add(g)
            n, d = name.get(g), dt_of.get(g)
            starts[n][r] += 1
            act = f.act.get(g)
            if ticks:
                ct, how = creation_tick(f.tick, r, f.stick.get(g), f.ctick.get(g), act, f.beh.get(g))
            else:
                ct = countdown_creation(f.tick, r, d)
                how = "countdown" if ct is not None else ("no_timer" if r == 0 else "other_start")
            src[how] += 1
            if how == "stagger":
                kids_act["stagger", n, act] += 1              # behaviour 11: stagger ms left, not an age
            elif how == "active_ms":                          # (f) the alternative (+1 tick) shown beside it
                for e in (0, 1):
                    kids_act["e", e, "n"] += 1
                    kids_act["e", e, "in"] += prev.tick < ct + e <= f.tick
                kids_act["first_active", n, act] += 1
            if ct is None:
                per[n][how] += 1
                continue
            c["timed"] += 1
            inside = prev.tick < ct <= f.tick
            c["in_gap"] += inside
            per[n]["in_gap" if inside else "out_of_gap"] += 1
            if r > 0 and d and ticks:              # (b) the countdown read back to that creation tick
                ctk = f.ctick.get(g)
                if ctk is not None and ctk >= 0:   # card-made: started at DeployTime, or longer (spell-carried)
                    k = (d - r) / BASE_STEP - (f.tick - ct)   # steps beyond the ticks since creation
                    if k < 0:                      # a start above DeployTime: the carrier's (Goblin Barrel goblins)
                        longer[n][r + BASE_STEP * (f.tick - ct + 1)] += 1
                        continue
                    c["cd_n"] += 1                 # k > 1 = the stamp is later than the countdown allows
                    credit[n, k] += 1
                    c["cd_ok"] += k in (0, 1)
                else:                              # spawned child: its start, assuming the first step on the creation tick
                    kids[n][r + BASE_STEP * (f.tick - ct + 1)] += 1
        seen.update(g for g in f.dep if prev is None)
        prev = f
    for f0, f1, dt in intervals(frames):
        for g, r1 in f1.dep.items():
            r0 = f0.dep.get(g)
            s0, s1 = f0.stick.get(g), f1.stick.get(g)
            if ticks and s0 is not None and s1 is not None:
                c["stamp_pairs"] += 1
                if s0 != s1:                        # (e) re-stamped in (f0, f1]: only a new deploy, inside the gap
                    c["chg_n"] += 1
                    c["chg_ok"] += f1.beh.get(g) == 4 and f0.tick < s1 + 1 <= f1.tick
            if r0 is None or r1 is None or r0 <= 0 or g in scaled:
                continue
            if r1 > 0:
                c["step_n"] += 1
                c["step_ok"] += r0 - r1 == BASE_STEP * dt
            else:                      # deploy ended in (f0, f1]: the countdown would reach 0 at f0 + r0 / 50
                c["end_n"] += 1
                c["end_ok"] += f0.tick < f0.tick + -(-r0 // BASE_STEP) <= f1.tick
    rate = c["in_gap"] / c["timed"] if c["timed"] else 0
    st_rate = c["state_ok"] / c["state_rows"] if c["state_rows"] else 0
    step_rate = c["step_ok"] / c["step_n"] if c["step_n"] else 1
    cd_rate = c["cd_ok"] / c["cd_n"] if c["cd_n"] else 1
    ok = (rate >= 0.95 and cd_rate >= 0.95 and step_rate >= 0.99 and c["end_ok"] == c["end_n"] and st_rate >= 0.99
          and c["chg_ok"] == c["chg_n"])
    how = ("deploy_tick_raw + 1 (deploying) / card_tick_raw + 1 / first - active_ms_raw / 50" if ticks
           else f"countdown only: first - (DeployTime - remaining) / 50 + {COUNTDOWN_CREDIT}")
    out = [f"V11 {verdict(ok, c['timed'] >= 20)} creation tick [{how}] inside (prev frame, first] {c['in_gap']}/"
           f"{c['timed']} = {rate:.3f} (need >= 0.95, >= 20 bodies; sources {dict(src)}); card-made countdown = "
           f"DeployTime started on it (step credit 0/1, not later) {c['cd_ok']}/{c['cd_n']} (need >= 0.95; longer "
           f"carrier starts apart: {sum(sum(v.values()) for v in longer.values())}); -50/tick while "
           f"deploying {c['step_ok']}/{c['step_n']}; "
           f"zero reached inside the gap {c['end_ok']}/{c['end_n']}; behaviour 4 <=> remaining > 0 {c['state_ok']}/"
           f"{c['state_rows']} ({st_rate:.4f}); deploy stamp changes {c['chg_n']} in {c['stamp_pairs']} sample pairs, all "
           f"a new deploy inside the gap: {c['chg_ok']}/{c['chg_n']}; null rows {c['null_rows']}/{c['rows']}"]
    out.append("   V11 per name (counts; first-sighting remaining values): " + "; ".join(
        f"{n}: {dict(p)} {dict(starts[n].most_common(4))}" for n, p in sorted(per.items(), key=lambda x: -sum(x[1].values()))))
    if credit:
        lag = sorted({n for (n, k) in credit if k == 0})
        out.append(f"   V11 countdown step credit on the creation tick (1 = first -50 on it, 0 = one tick later): "
                   f"{sorted(credit.items(), key=lambda x: (str(x[0][0]), x[0][1]))}; credit-0 names {lag}")
    if kids or longer:
        out.append("   V11 deploy starts other than DeployTime, start ms (first step on the creation tick assumed): spawned "
                   "children (card_tick -1) " + "; ".join(f"{n}: {dict(k.most_common(4))}" for n, k in sorted(kids.items()))
                   + " | card-made, longer than DeployTime " + "; ".join(f"{n}: {dict(k.most_common(4))}"
                                                                     for n, k in sorted(longer.items())))
    if any(f.act for f in frames):
        e_rates = {e: (kids_act["e", e, "in"], kids_act["e", e, "n"]) for e in (0, 1)}
        first_act = collections.defaultdict(collections.Counter)
        for (kind, n, v), k in kids_act.items():
            if kind in ("first_active", "stagger"):
                first_act[kind, n][v] += k
        out.append(f"   V11 never-deploying children (no stamp, card_tick -1): creation = first - active_ms_raw / 50 + e "
                   f"inside the gap: e=0 (used) {e_rates[0][0]}/{e_rates[0][1]}, e=1 {e_rates[1][0]}/{e_rates[1][1]}; first-sight "
                   "active / stagger ms per name " + "; ".join(f"{k[1]} {k[0]}: {dict(v.most_common(4))}"
                                                            for k, v in sorted(first_act.items(), key=lambda x: x[0][1])))
    out.append(f"   V11 state/countdown disagreements (name, behaviour, remaining>0): {bad_rows.most_common(8)}")
    return out


# Phase 3c (READER_PHASE3C.md): shield, lifetime decay, spawner timer, attack state of a disabled body. Laws (static, the
# capture checks them): a shield absorbs damage before hp; a LifeTime building loses `decay_rate` hundredths of a hp a tick
# into an accumulator, whole hp coming off the hp pool, never while deploying; a spawner's timer drops 50 a tick unbuffed and
# on reaching 0 spawns and re-arms by SpawnInterval (inside a wave) or SpawnPauseTime (after the wave's last spawn).
def decay_rate(max_hp, life_time):
    """Lifetime decay per tick in hundredths of a hp, as the game sets it when the HP component is made."""
    return max_hp * 100000 // life_time // 20


def life_left_ticks(hp, acc, rate):
    """Ticks of pure lifetime decay before hp reaches 0 (no damage, no heal); None without a decay."""
    return -(-(hp * 100 - acc) // rate) if rate and rate > 0 else None


def spawn_step_kind(t0, t1, dt, d, step=BASE_STEP):
    """Classify one sample pair of a spawner's timer: step (-50 x dt), held, rearm_interval / rearm_pause (one spawn
    inside the gap), rearm_2 (two), other."""
    delta = t1 - t0
    if delta == -step * dt:
        return "step"
    if delta == 0:
        return "held"
    extra = delta + step * dt
    iv, pz = d.get("SpawnInterval") or 0, d.get("SpawnPauseTime") or 0
    if extra in (iv, pz):
        return "rearm_interval" if extra == iv else "rearm_pause"
    if extra in (2 * iv, iv + pz):
        return "rearm_2"
    return "other"


def hidden_lines(frames, defs, def_of, name):
    """V12 (phase 3c): (a) shield: a body whose definition has ShieldHitpoints starts with shield == shield max > 0, and
    its hp stays at max while the shield is up; no-shield bodies read 0 / 0; (b) lifetime decay rate == the
    definition formula, and every sample pair of an active decaying building drains exactly dt x rate hundredths
    (hp x 100 + accumulator) unless damaged (more) -- never less, except a heal; an undamaged one disappears where the
    remaining-life formula says; (c) spawner timer: -50 a tick or one re-arm by SpawnInterval / SpawnPauseTime, and the
    first active value vs SpawnStartTime (derivable?); (d) attack_disabled rows (attack bit clear) and their buffs."""
    if not any(f.row3c for f in frames):
        return ["V12 SKIP no phase-3c fields in this capture (pre-3c probe)"]
    D = lambda g: defs.get(def_of.get(g), {})
    # spawners = bodies whose timer moves at least once (a definition can carry spawn values without a spawn character:
    # the Mega Knight's timer never moves)
    tvals = collections.defaultdict(set)
    for f in frames:
        for g, r in f.row3c.items():
            tvals[g].add(r.get("spawn_timer_ms_raw"))
    spawners = {g for g, v in tvals.items() if len(v - {None}) > 1}
    sh, dc, sp, dis, lt_t = (collections.Counter() for _ in range(5))
    ratio, rate_bad, sp_bad, sp_first, dis_buffs = collections.defaultdict(set), [], [], collections.Counter(), collections.Counter()
    first, rated, spf, last_exact, life_end, pend = set(), set(), set(), {}, collections.Counter(), {}
    pend_d = {}
    prev = None
    for f in frames:
        for g, r in f.row3c.items():
            e, d = f.ents.get(g), D(g)
            if e is None:
                continue
            if r["shield_hp_raw"] is None:
                sh["null_rows"] += 1
                continue
            s, smax, hp, mx = r["shield_hp_raw"], r["shield_max_raw"], e["hp"], e["max_hp"]
            if (d.get("ShieldHitpoints") or 0) > 0:
                if g not in first:               # native shields start full; an ability shield (Hero Knight) at 0
                    first.add(g); sh["first"] += 1; sh["first_full" if s == smax > 0 else "first_empty" if s == 0 < smax else "first_bad"] += 1
                    ratio[name.get(g)].add(round(smax / d["ShieldHitpoints"], 3))
            elif smax > 0:
                sh["other_shield_bodies"] += 1
            elif not f.buffs.get(g):
                sh["none_rows"] += 1; sh["none_zero"] += s == 0 and smax == 0
            lt = d.get("LifeTime") or 0
            if lt > 0 and g not in rated:
                rated.add(g); dc["rate_n"] += 1
                if r["life_decay_per_tick_raw"] == decay_rate(mx, lt):
                    dc["rate_ok"] += 1
                else:
                    rate_bad.append((name.get(g), mx, lt, r["life_decay_per_tick_raw"]))
            if r.get("attack") is None and r.get("attack_disabled") is not None:
                dis["rows"] += 1
                for b in f.buffs.get(g) or ():
                    dis_buffs[b["name"]] += 1
                if not f.buffs.get(g):
                    dis_buffs["(no buff) behaviour %s deploying %s" % (f.beh.get(g), (r.get("deploy_remaining_raw") or 0) > 0)] += 1
        if prev is not None and f.tick > prev.tick:     # repeated-tick frames (match end) carry no step
            dt = f.tick - prev.tick
            for g, r0 in prev.row3c.items():
                d, r, e0, e = D(g), f.row3c.get(g), prev.ents.get(g), f.ents.get(g)
                lt = d.get("LifeTime") or 0
                if r is None:                    # gone: was its last pair a pure drain, and does the formula place the end?
                    if g in last_exact and lt > 0:
                        hp0, acc0, rate0 = last_exact[g]
                        left = life_left_ticks(hp0, acc0, rate0)
                        life_end["in_gap" if left is not None and left <= dt else "later_or_killed"] += 1
                    continue
                if None in (r0["life_decay_acc_raw"], r["life_decay_acc_raw"]) or e0 is None or e is None:
                    continue
                if r0["shield_hp_raw"] > 0 and r["shield_hp_raw"] > 0:   # shield up on both: hp cannot drop
                    sh["up_pairs"] += 1; sh["up_hp_kept"] += e["hp"] >= e0["hp"]
                    sh["up_absorbed"] += r["shield_hp_raw"] < r0["shield_hp_raw"]
                elif r0["shield_hp_raw"] == 0 < r["shield_hp_raw"]:
                    sh["raised"] += 1
                active = not (r0.get("deploy_remaining_raw") or r.get("deploy_remaining_raw")) and \
                    f.beh.get(g) not in (4, 6, 11) and prev.beh.get(g) not in (4, 6, 11)
                timer_ran = r["life_timer_ms_raw"] - r0["life_timer_ms_raw"] == BASE_STEP * dt
                if lt > 0 and timer_ran and active:
                    lt_t["timer"] += 1           # the timer-mode lifetime ran instead (flag + an unresolved body condition)
                elif lt > 0 and active and e["hp"] > 0:
                    drain = (e0["hp"] - e["hp"]) * 100 + r["life_decay_acc_raw"] - r0["life_decay_acc_raw"]
                    want = dt * r["life_decay_per_tick_raw"]
                    k = "exact" if drain == want else "more" if drain > want else "less"
                    if k == "less" and drain == 0:
                        k = "held"                   # nothing moved: the match-end freeze (the battle tick stops)
                    if k == "less" and any(b["config"].get("HealPerSecond") for b in (f.buffs.get(g) or ())):
                        k = "less_healed"
                    q = pend_d.pop(g, None)          # the label artefact: two adjacent pairs, opposite errors, lawful sum
                    if k in ("less", "more") and q and {k, q[0]} == {"less", "more"} and drain + q[1] == want + q[2]:
                        dc[q[0]] -= 1; dc["label_artefact"] += 2; k = None
                    else:
                        dc[k] += 1
                    pend_d[g] = (k, drain, want)
                    if k == "exact":
                        last_exact[g] = (e["hp"], r["life_decay_acc_raw"], r["life_decay_per_tick_raw"])
                    else:
                        last_exact.pop(g, None)
                if g in spawners and \
                        r0.get("spawn_timer_ms_raw") is not None and r.get("spawn_timer_ms_raw") is not None:
                    k = spawn_step_kind(r0["spawn_timer_ms_raw"], r["spawn_timer_ms_raw"], dt, d)
                    buffed = bool(f.buffs.get(g) or prev.buffs.get(g))
                    dep = bool(r0.get("deploy_remaining_raw") or r.get("deploy_remaining_raw"))
                    how = "deploying" if dep else "buffed" if buffed else "clean"
                    q = pend.pop(g, None)            # the sampling artefact: one frame's state a tick off its label makes
                    if k == "other" and q and q[0] == "other" and                             spawn_step_kind(q[1], r["spawn_timer_ms_raw"], q[2] + dt, d) != "other":
                        sp[("other", q[3])] -= 1     # two adjacent 'other' pairs whose sum is lawful
                        sp[("label_artefact", q[3])] += 1; k = "label_artefact"
                        if sp_bad and sp_bad[-1][0] == name.get(g):
                            sp_bad.pop()
                    sp[(k, how)] += 1
                    pend[g] = (k, r0["spawn_timer_ms_raw"], dt, how)
                    if k == "other" and how == "clean" and len(sp_bad) < 8:
                        sp_bad.append((name.get(g), prev.tick, f.tick, r0["spawn_timer_ms_raw"], r["spawn_timer_ms_raw"]))
                    if not dep and g not in spf and r0.get("deploy_remaining_raw") == 0 and not buffed:
                        spf.add(g)               # first active sample: SpawnStartTime - timer in ticks vs ticks deployed
                        st0 = d.get("SpawnStartTime")
                        if st0 is not None and r0.get("active_ms_raw") is not None:
                            sp_first[(name.get(g), (st0 - r0["spawn_timer_ms_raw"]) // BASE_STEP - r0["active_ms_raw"] // BASE_STEP)] += 1
        prev = f
    ok_a = not sh["first_bad"] and sh["up_hp_kept"] == sh["up_pairs"] and sh["none_zero"] == sh["none_rows"]
    out = [f"V12a {verdict(ok_a, sh['up_pairs'] >= 10 and sh['up_absorbed'] >= 1)} shield: first sight full {sh['first_full']} / empty (ability "
           f"shield) {sh['first_empty']} / bad {sh['first_bad']}; shield raised later {sh['raised']}; pairs with the shield up "
           f"{sh['up_pairs']}: hp not lost {sh['up_hp_kept']}, shield absorbed {sh['up_absorbed']}; bodies with a shield and no "
           f"ShieldHitpoints rows {sh['other_shield_bodies']}; no-shield bodies 0/0 {sh['none_zero']}/{sh['none_rows']}, "
           f"null rows {sh['null_rows']}; shield max / ShieldHitpoints per name {dict((k, sorted(v)) for k, v in ratio.items())}"]
    n_b = dc["exact"] + dc["more"] + dc["less"]
    out.append(f"V12b {verdict(dc['rate_ok'] == dc['rate_n'] and dc['less'] == 0 and dc['exact'] > 0, dc['rate_n'] >= 1 and n_b >= 20)} "
               f"lifetime decay: rate == formula {dc['rate_ok']}/{dc['rate_n']} {rate_bad[:4]}; pairs drained exactly dt x rate "
               f"{dc['exact']}, more (damage) {dc['more']}, less {dc['less']} (+ healed {dc['less_healed']}, label artefact pairs {dc['label_artefact']}, held at match end {dc['held']}); undamaged "
               f"to the end and gone where the formula says {life_end['in_gap']}/{sum(life_end.values())}; pairs where the "
               f"lifetime timer ran (+50/tick) instead {lt_t['timer']}")
    clean = {k: v for (k, how), v in sp.items() if how == "clean"}
    n_c = sum(clean.values())
    out.append(f"V12c {verdict(clean.get('other', 0) <= 0.005 * n_c and clean.get('step', 0) > 0, n_c >= 20)} spawner timer "
               f"({len(spawners)} spawner bodies: {sorted(collections.Counter(name.get(g) for g in spawners).items())}) (clean pairs) {clean}; deploying {dict((k, v) for (k, how), v in sp.items() if how == 'deploying')}; buffed "
               f"{dict((k, v) for (k, how), v in sp.items() if how == 'buffed')}; other rows {sp_bad[:6]}; first active sample "
               f"(SpawnStartTime - timer)/50 - active/50 per name {dict(sp_first)}")
    out.append(f"V12d INFO attack_disabled rows {dis['rows']}; their buffs {dis_buffs.most_common(8)}")
    return out


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
    lt_of = {g: defs[d]["LoadTime"] for g, d in def_of.items() if d in defs}
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

    # attack-instant events: projectile launches (shooters), the load-timer re-arm (non-shooters with LoadTime > 0:
    # the exact fire tick) and clean hp drops of the target (other non-shooters). A target's hp drop is not a clean
    # marker: a decaying building target (the X-Bow, 5-6 hp every 2 ticks) and other attackers make most of the
    # opponent Tesla's 1016 drops (115 of 127 non-fire drops on the X-Bow)
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
            if lt_of.get(g, 0) > 0:
                fire = rearm(f0, f1, g, lt_of[g])
                if fire:
                    ks = range(fire[0] - f0.tick, fire[1] - f0.tick + 1)
                    events[name.get(g)].append(candidates(lin[0], lin[1], dt, hs_of[g], ks))
                    ev_ticks[name.get(g)].append(fire[1])
            elif clean_drop(f0, f1, g, f0.att[g]["target_gen"]):
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

    out.append(phase_line("V5", "Xbow"))

    # V5L lock rule (owner 10-16): an attacker locked on a crown tower (in its attack: progress > 0) keeps it while
    # troops come into range; it switches only after a stun / freeze / taunt reset. A switch away from a still-standing
    # tower with no reset buff on the attacker in the last RESET_WINDOW ticks (and not to a Hero Knight) is a FAIL.
    last_reset, c5, rows5 = {}, collections.Counter(), []
    for f0, f1, dt in intervals(frames):
        for f in (f0, f1):
            for g, bs in f.buffs.items():
                if any(is_reset_buff(b) for b in bs or []):
                    last_reset[g] = f.tick
        for g, a1 in f1.att.items():
            a0 = f0.att.get(g)
            if not a0 or not a1 or name.get(g, "").endswith("Tower") or a0["progress_raw"] <= 0:
                continue
            tw = a0["target_gen"]
            if tw in (None, "unlisted") or not name.get(tw, "").endswith("Tower") or tw not in f1.ents:
                continue
            reset = f1.tick - last_reset.get(g, -10**9) <= RESET_WINDOW
            y = a1["target_gen"]
            if y == tw:
                c5["held"] += 1
                c5["held_troop_in_range"] += troop_in_range(f1, g, by_name.get(name.get(g), {}).get("Range"))
                c5["held_through_reset"] += reset
                continue
            taunt = name.get(y) == "KnightHero"
            c5["switch_after_reset" if reset or taunt else "switch_no_reset"] += 1
            rows5.append(f"{'ok ' if reset or taunt else 'NO RESET '}{name.get(g)} t{f1.tick} ({V(f1.tick)}) "
                         f"{name.get(tw)} -> {name.get(y, y)}{' (taunt)' if taunt else ''}")
    lockers = sorted({name.get(g) for f in frames for g, a in f.att.items()
                      if a and a["progress_raw"] > 0 and name.get(a["target_gen"], "").endswith("Tower")
                      and not name.get(g, "").endswith("Tower")})
    out.append(f"V5L {verdict(c5['switch_no_reset'] == 0, c5['held'] >= 10)} tower lock: held {c5['held']} intervals "
               f"(an enemy troop within Range in {c5['held_troop_in_range']}, a reset buff present in "
               f"{c5['held_through_reset']}); switches without stun/freeze/taunt {c5['switch_no_reset']} (need 0); "
               f"switches after a reset {c5['switch_after_reset']}; lockers {lockers}; {rows5[:6]}")

    # V6 buffed step law: frozen -> 0, Hero IW slow (-30) -> 35, between refreshes
    c6 = collections.Counter()
    for f0, f1, dt in intervals(frames):
        for g, a1 in f1.att.items():
            a0, b0, b1 = f0.att.get(g), f0.buffs.get(g), f1.buffs.get(g)
            if not a0 or not a1 or not b1 or a0["target_gen"] != a1["target_gen"] or a0["target_gen"] is None:
                continue
            if a0["seq_idx"] not in (-1, 0) or a0["progress_raw"] <= 0 or not no_refresh(b0, b1):
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
            if not a0 and any(b["config"]["HitSpeedMultiplier"] <= -100 for b in f0.buffs.get(g) or []):
                # the component is absent while frozen and comes back with the HELD progress (Tesla 1850 -> 1950
                # across a 10-tick freeze): a resume, not a fresh cycle
                first[nm]["resume_after_freeze"] += 1
                continue
            acq = next((s.tick for s in reversed(series[:k]) if not s.att[g] or s.att[g]["target_gen"] != v), None)
            hit, conf, j = None, False, k
            while j + 1 < len(series) and series[j + 1].att[g] and series[j + 1].att[g]["target_gen"] == v:
                h0, h1 = series[j], series[j + 1]
                if g in shooters:
                    if any(x[0] is h0 and x[1] is h1 for x in launch_at[g]):
                        hit = (h0.tick + 1, h1.tick)
                elif lt_of.get(g, 0) > 0:
                    hit = rearm(h0, h1, g, lt_of[g])
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
                # (a) entry credit: progress on the entry frame = LoadTime + step -> p1 = LoadTime + step x (1 + ticks
                #     since entry), those ticks in [0, dt - 1];
                # (b) the hit: on the tick progress reaches the next HitSpeed multiple -> f1 + (m - p1) / 50 must
                #     fall inside the observed launch / hp-drop bracket (width = one sample gap).
                # Both use the body's step at the entry sample (35 under the Ice Wizard slow: credit LoadTime + 35, the
                # hit on the tick that crosses the multiple); a buff change before the hit is not modelled.
                hs, lt = srow["hit_speed_ms"], srow.get("load_time_ms") or 0
                s = step_law(f1.buffs.get(g)) or BASE_STEP
                since, rem = divmod(p1 - lt - s, s)
                credit_ok = rem == 0 and 0 <= since < dt
                need = -(-p1 // hs) * hs - p1                 # progress still to go to the next HitSpeed multiple
                sim_hit = f1.tick - (-need // s)               # + ceil(need / s) ticks
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
                   f"{n}: SIM {sim_first_hit_ticks(sim_row(srows, n))} ticks, credit LoadTime+step {c['credit_ok']}/"
                   f"{c['with_pred']}, hit at next HitSpeed multiple {c['hit_ok']}/{c['with_pred']}, SIM delay in the "
                   f"model-free bracket {c['bracket_ok']}/{c['with_pred']} (measured {c['n']}, interrupted "
                   f"{c['interrupted']}, confounded {c['confounded']}, reentry {c['reentry_load_running']}, resumed after a freeze {c['resume_after_freeze']})"
                   for n, c in sorted(first.items()) if c["n"] or c["interrupted"]))
    out.append(f"   V10 rows (first 10): {rows10[:10]}")

    out += deploy_lines(frames, defs, def_of, name)
    out += hidden_lines(frames, defs, def_of, name)

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
