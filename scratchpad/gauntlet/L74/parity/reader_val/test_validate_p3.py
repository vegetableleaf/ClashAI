"""Synthetic check of validate_p3.py: a tick-level toy battle that follows the SIM's progress_credit attack cycle is
sampled like the 100 ms probe (2- and 3-tick gaps) and must PASS V1-V6, V8-V10 (V7 SKIP: no Hero Knight); a wrong
definition and early first hits must FAIL the checks that own them.

    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/parity/reader_val/test_validate_p3.py
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_p3 as vp  # noqa: E402

SIM, _ = vp.sim_cards(vp.SIM_CARDS)
NAMES = ["KingTower", "PrincessTower", "Knight", "Goblin", "Xbow", "Tesla", "Skeleton", "Giant"]


def defs(over=None):
    out = []
    for i, n in enumerate(NAMES):
        r = SIM[n]
        d = {"definition_id": 1000 + i, "name": n, "HitSpeed": r["hit_speed_ms"], "Range": r.get("range_milli") or 0,
             "MinimumRange": r.get("minimum_range_milli") or 0, "SightRange": r.get("sight_range_milli") or 0,
             "LoadTime": r.get("load_time_ms") or 0, "LoadFirstHit": int(bool(r.get("load_first_hit"))),
             "LoadAfterRetarget": 0, "ActivationTime": 0, "AttackDashTime": 0}
        d.update((over or {}).get(n, {}))
        out.append(d)
    return out


def battle(hit_shift=0, over=None, xbow=None, slow=False):
    """-> list of frame dicts. hit_shift moves every Knight hit earlier by that many ticks. slow: every Knight carries
    IceWizardHeroSlow (-30): +35/tick, hits on the tick that crosses a HitSpeed multiple, overshoot carried (live and
    SIM, ATTACK_PHASE_1016.md). Knights re-arm their load timer to LoadTime on entry and on every hit. xbow: None = the X-Bow
    keeps the tower while a Skeleton walks into its range; "bare" = it switches to the Skeleton at t210 with no reset;
    "frozen" = the same switch right after a Freeze on the X-Bow (t200-209)."""
    D = {d["name"]: d for d in defs(over)}
    att, ents, side, name, buffs, proj, pos = {}, {}, {}, {}, {}, {}, {}

    def body(g, n, s, hp=1000):
        ents[g] = hp
        side[g], name[g] = s, n
        pos.setdefault(g, (9000, 16000))
        att.setdefault(g, None)
    for g, n, s in ((5000000, "KingTower", 0), (5000001, "PrincessTower", 0), (5000003, "KingTower", 1),
                    (5000004, "PrincessTower", 1)):
        pos[g] = (3500 if g % 3 else 9000, 25500 if s else 6500)
        body(g, n, s, 3000)
        att[g] = dict(target_gen=None, progress=0, load=0)
    frames, nkey, sample = [], [4000000], 0
    entries = [100 + 7 * i + (i % 2) for i in range(5)]
    for t in range(0, 330):
        # five Knights (5000100+i), each on its own Goblin (5000200+i); SIM cycle: entry LoadTime+50, hit at k*HitSpeed
        for i, e in enumerate(entries):
            k, v = 5000100 + i, 5000200 + i
            if t == e - 15:
                body(k, "Knight", 0)
                body(v, "Goblin", 1)
                att[v] = dict(target_gen=None, progress=0, load=0)
            if slow and t >= e - 15:
                buffs[k] = [("IceWizardHeroSlow", -30, 99999 - 50 * t)]
            if t >= e - 6:
                lt, hs, s = D["Knight"]["LoadTime"], D["Knight"]["HitSpeed"], 35 if slow else 50
                p = 0 if t < e else lt + s + s * (t - e)
                q = p + 50 * hit_shift
                hit = t >= e and q // hs > (q - s) // hs
                load = lt if t == e or hit else max(0, (att[k] or {}).get("load", 0) - 50)
                att[k] = dict(target_gen=v, progress=p, load=load)
                if hit and ents[v] > 100:
                    ents[v] -= 100
        # X-Bow on the enemy princess tower: entry 151, LoadTime 0 -> progress 50, launch at k*400
        if t == 140:
            pos[5000050] = (3500, 16000)
            body(5000050, "Xbow", 0)
        if t == 195:                     # a Skeleton walks into the X-Bow's range (9.5k of 11.5k) and stays
            pos[5000080] = (3500, 18000)
            body(5000080, "Skeleton", 1)
            att[5000080] = dict(target_gen=None, progress=0, load=0)
        if xbow == "frozen":
            buffs[5000050] = [("Freeze", -100, 500 - 50 * (t - 200))] if 200 <= t < 210 else []
        if t >= 145:
            p = 0 if t < 151 else D["Xbow"]["LoadTime"] + 50 + 50 * (t - 151)
            tgt = 5000080 if xbow and t >= 210 else 5000004
            att[5000050] = dict(target_gen=tgt, progress=p, load=0)
            if p and p % D["Xbow"]["HitSpeed"] == 0:
                nkey[0] += 1
                proj[nkey[0]] = [5000050, 5000004, 4]
        # Tesla: S1 dies at 160 (retarget to S2 after a kill), switch to S3 at 200 while S2 lives
        if t == 110:
            body(5000060, "Tesla", 0)
            for g in (5000061, 5000062, 5000063):
                body(g, "Skeleton", 1)
                att[g] = dict(target_gen=None, progress=0, load=0)
        if t >= 120:
            tgt, since = (5000061, 120) if t < 160 else ((5000062, 160) if t < 200 else (5000063, 200))
            prev = None if t < 160 else (5000061 if t < 200 else 5000062)
            att[5000060] = dict(target_gen=tgt, prev=prev, progress=50 * (t - since + 1), load=0)
        if t == 160:
            del ents[5000061]
        # Giant on the own princess tower: frozen 150-189 (progress held), then Hero IW slow 200-259 (+35/tick)
        if t == 90:
            body(5000070, "Giant", 1)
        if t >= 100:
            a = att[5000070] or dict(target_gen=5000001, progress=0, load=0)
            fr, sl = 150 <= t < 190, 200 <= t < 260
            buffs[5000070] = ([("IceWizardHero_FreezeBuff", -100, 2000 - 50 * (t - 150))] if fr else
                              [("IceWizardHeroSlow", -30, 3000 - 50 * (t - 200))] if sl else [])
            a = dict(a, progress=a["progress"] + (0 if fr else 35 if sl else 50))
            att[5000070] = a
        for key in list(proj):
            proj[key][2] -= 1
            if proj[key][2] < 0:
                del proj[key]
        if t % 2 or (t % 18 == 0 and t):
            continue                     # sample every 2 ticks, a 3-tick gap every 9th sample
        sample += 1
        A = lambda g: "0x%x" % (0x700000000000 + g * 16)  # noqa: E731
        bodies = []
        for g in ents:
            a = att.get(g)
            bodies.append({"generation": g, "definition_id": D[name[g]]["definition_id"],
                           "attack": None if a is None else {
                               "target_gen": a["target_gen"], "prev_target_gen": a.get("prev"), "seq_idx": -1,
                               "progress_raw": a["progress"], "load_raw": a["load"], "pre_raw": 0,
                               "activation_raw": 0, "flags_raw": [0] * 5}})
            if a is None:
                bodies[-1]["null_reason"] = "no_component"
        units = [{"generation": g, "name": name[g], "side": side[g],
                  "buffs": [{"name": b, "remaining_ms_raw": r, "config": {"HitSpeedMultiplier": m}}
                            for b, m, r in buffs.get(g, [])]} for g in ents]
        frames.append({"game_tick": t, "battle_active": True, "read_us": 400 + sample % 50,
                       "entities": [{"address": A(g), "category": g, "side": side[g], "hp": ents[g],
                                     "x": pos[g][0], "y": pos[g][1]} for g in ents],
                       "projectiles": [{"generation_key": k, "source": A(s), "target": A(v)} for k, (s, v, _) in proj.items()],
                       "effects": [], "phase2": {"units": units},
                       "phase3": {"valid": sample != 7, "bodies": bodies, "defs": defs(over) if sample == 1 else []}})
    return frames


BASE = 50


def deploy_battle(stamp_shift=0, step=50, restamp=False):
    """Phase 3b toy (laws measured live 10-17): a body made while the battle tick reads X is first visible in frame X+1;
    it stamps deploy_tick = X (kept for life) and, if card-made, card_tick = X (else -1). Card troops take their first -50 on the
    creation tick (credit 1), IW-style late bodies one tick later (credit 0); children start at 500; at 0 the behaviour
    leaves 4. stamp_shift moves every deploy stamp; restamp re-stamps every Knight mid-life with no new deploy (a
    stamp that follows the behaviour, which the live bodies never do); step is the countdown step."""
    D = {d["name"]: d for d in defs()}
    for d in D.values():
        d.update(DeployTime=1000, DeployTimerDelay=0, DeployTimeAffectedByCharacterSpeed=0)
    bodies = [(5000000 + i, "PrincessTower", None, None, None) for i in range(2)]
    for i in range(24):                                  # (gen, name, created frame tick, start ms, credit, card-made)
        bodies.append((5000100 + i, "Knight", 10 + 7 * i, 1000, (1, True)))
    for i in range(4):
        bodies.append((5000200 + i, "Giant", 13 + 31 * i, 1000, (0, True)))
        bodies.append((5000300 + i, "Skeleton", 15 + 29 * i, 500, (1, False)))
        bodies.append((5000400 + i, "Goblin", 20 + 23 * i, 0, (1, False)))
    frames, sample = [], 0
    for t in range(0, 220):
        if t % 2 or (t % 18 == 0 and t):
            continue
        sample += 1
        ents, rows = [], []
        for g, n, c, start, how in bodies:
            if c is not None and t < c:
                continue
            if c is None:
                r, beh, st_, ct, act = 0, 0, 0, -1, 0
            else:
                credit, card = how
                ran = max(0, t - c + credit)
                r = max(0, start - step * ran) if start else 0
                end = c - credit + -(-start // step) if start else None    # frame tick on which it reaches 0
                beh = 4 if r > 0 else 1
                st_ = (c - 1 + stamp_shift if not (restamp and n == "Knight" and r == 0) else end - 1) if start else 0
                ct = c - 1 if card else -1
                act = BASE * max(0, t - (end if start else c))      # e = 0: 0 on the creation / deploy-end frame
            ents.append({"address": "0x%x" % (0x700000000000 + g * 16), "category": g, "side": 0, "hp": 500,
                         "x": 9000, "y": 9000, "behavior_state_raw": beh})
            rows.append({"generation": g, "definition_id": D[n]["definition_id"], "deploy_remaining_raw": r,
                         "deploy_tick_raw": st_, "card_tick_raw": ct, "active_ms_raw": act, "attack": None, "null_reason": "no_component"})
        frames.append({"game_tick": t, "battle_active": True, "read_us": 450, "entities": ents, "projectiles": [],
                       "effects": [], "phase2": {"units": [{"generation": e["category"], "name": next(
                           b[1] for b in bodies if b[0] == e["category"]), "side": 0, "buffs": []} for e in ents]},
                       "phase3": {"valid": True, "bodies": rows, "defs": list(D.values()) if sample == 1 else []}})
    return frames


def verdicts(frames, **kw):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "frames.jsonl")
        with open(p, "w") as h:
            for f in frames:
                h.write(json.dumps(f) + "\n")
        fr, n = vp.load(p)
        lines = vp.run(fr, n, None, tables=os.path.join(d, "no_tables"), **kw)
    return {ln.split()[0]: ln for ln in lines if re.match(r"V\d+L? ", ln)}, lines


def main():
    v, lines = verdicts(battle())
    for k in ("V1", "V2", "V3", "V4", "V5", "V6", "V8", "V9", "V10"):
        assert v[k].split()[1] == "PASS", "\n".join(lines)
    assert v["V7"].split()[1] == "SKIP", v["V7"]
    assert v["V5L"].split()[1] == "PASS" and "switches without stun/freeze/taunt 0" in v["V5L"], v["V5L"]
    assert int(re.search(r"an enemy troop within Range in (\d+)", v["V5L"]).group(1)) > 0, v["V5L"]
    # the X-Bow lock rule: a bare switch to a troop FAILs, the same switch right after a Freeze is expected
    bare, lines = verdicts(battle(xbow="bare"))
    assert bare["V5L"].split()[1] == "FAIL" and "NO RESET Xbow t210" in bare["V5L"], bare["V5L"]
    froz, lines = verdicts(battle(xbow="frozen"))
    assert froz["V5L"].split()[1] == "PASS" and "switches after a reset 1" in froz["V5L"], froz["V5L"]
    assert re.search(r"events=(\d+) fixed_phase=0 support=\1/\1 ", v["V3"]), v["V3"]
    assert "frozen: " in v["V6"] and "slow35: " in v["V6"], v["V6"]
    assert "Knight: SIM 9 ticks, credit LoadTime+step 5/5, hit at next HitSpeed multiple 5/5" in v["V10"], v["V10"]
    assert "Xbow: SIM 7 ticks, credit LoadTime+step 1/1, hit at next HitSpeed multiple 1/1" in v["V10"], v["V10"]
    # a definition that disagrees with the device row and the SIM row
    bad, lines = verdicts(battle(over={"Knight": {"LoadTime": 600}}))
    assert bad["V1"].split()[1] == "FAIL" and bad["V9"].split()[1] == "FAIL", "\n".join(lines)
    assert "('Knight', 'LoadTime', 600, 700)" in bad["V9"], bad["V9"]
    # Knights hitting 2 ticks early: the phase is still fixed (V3 records it), the SIM first-hit delay is not met
    early, lines = verdicts(battle(hit_shift=2))
    assert early["V3"].split()[1] == "PASS" and "fixed_phase=1100" in early["V3"], early["V3"]
    assert early["V10"].split()[1] == "FAIL" and re.search("Knight: .*?hit at next HitSpeed multiple [01]/5", early["V10"]), "\n".join(lines)
    # slowed Knights (+35/tick): hits on the crossing tick, remainders 0..30 carried -- still ONE phase (0) under the
    # crossing model (the old exact-phase model scattered them over 5..30), first hit credit LoadTime + 35
    sl, lines = verdicts(battle(slow=True))
    assert sl["V3"].split()[1] == "PASS" and re.search(r"events=(\d+) fixed_phase=0 support=\1/\1 ", sl["V3"]), "\n".join(lines)
    assert "Knight: SIM 9 ticks, credit LoadTime+step 5/5, hit at next HitSpeed multiple 5/5" in sl["V10"], sl["V10"]
    # 1190 -> 1225 passes phase 0 (the live hit, remainder 25); 1225 -> 1260 passes phase 50 only
    assert vp.candidates(1190, 35, 1, 1200) == {0} and vp.candidates(1225, 35, 1, 1200) == {50}, "crossing model"
    assert vp.candidates(1150, 50, 1, 1200) == {0} and vp.candidates(1100, 50, 2, 1200) == {1150, 0}
    # phase 3b: a capture without the deploy fields skips V11; the measured laws pass; a stamp one tick late (outside
    # the gap for every body first seen on its creation frame) or a -40 step fails
    assert v["V11"].split()[1] == "SKIP", v["V11"]
    dv, lines = verdicts(deploy_battle())
    assert dv["V11"].split()[1] == "PASS", "\n".join(lines)
    assert re.search(r"inside \(prev frame, first\] (\d+)/\1 = 1\.000", dv["V11"]), dv["V11"]
    assert "creation = first - active_ms_raw / 50 + e inside the gap: e=0 (used) 4/4, e=1 2/4" in "\n".join(lines), "\n".join(lines)
    assert "'active_ms': 4" in dv["V11"] and "credit-0 names ['Giant']" in "\n".join(lines), "\n".join(lines)
    late, lines = verdicts(deploy_battle(stamp_shift=1))
    assert late["V11"].split()[1] == "FAIL", late["V11"]
    moved, lines = verdicts(deploy_battle(restamp=True))
    assert moved["V11"].split()[1] == "FAIL" and "all a new deploy inside the gap: 0/24" in moved["V11"], moved["V11"]
    slow, lines = verdicts(deploy_battle(step=40))
    assert slow["V11"].split()[1] == "FAIL" and "-50/tick while deploying 0/" in slow["V11"], slow["V11"]
    assert vp.countdown_creation(101, 950, 1000) == 101 and vp.countdown_creation(101, 900, 1000) == 100
    assert vp.countdown_creation(101, 0, 1000) is None and vp.countdown_creation(101, 1200, 1000) is None
    assert vp.creation_tick(101, 950, 99, -1) == (100, "deploy_tick") and vp.creation_tick(101, 0, 0, 77) == (78, "card_tick")
    assert vp.creation_tick(101, 0, 0, -1, 100, 1) == (99, "active_ms") and vp.creation_tick(101, 0, 0, -1, 100, 11) == (None, "stagger")
    assert vp.creation_tick(101, 0, 0, -1) == (None, "no_tick") and vp.creation_tick(101, None, 0, -1) == (None, "null")
    print("VALIDATE_P3_SYNTHETIC_OK: 10 scenarios;", v["V3"][:60])


if __name__ == "__main__":
    main()
