"""S1-S8 of READER_STREAM_SPEC.md section 7: the merged reader's stream (a live_play --log-frames log run with the merged
reader as the main reader) against the side probe's capture of the same battle. Layout-free: it reads only the JSON
both readers already emit (bodies keyed by generation id; runtime addresses only as in-frame join keys, never printed).

    python validate_stream.py LIVE_LOG [--probe P3_FRAMES_JSONL] [--sha-receipt SHA --sha-device SHA --build-checked]
                              [--pgrep-after FILE] [--s7-frames N]

S1 hashes (+ the lead's build check), S2 budget, S3 v2 rows vs the probe, S4 cue fields vs the probe, S5 validate_p3 on
the stream, S6 SKIP (needs the live cue extractor, spec section 5), S7 BoardState with vs without the cue blocks,
S8 no reader left after the match (FILE = the post-match `pgrep -f` output; empty = none). Exit 1 if any check FAILs.
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[4]))

BUDGET = dict(read_us_median=600, read_us_p95=1300, gap2=0.96, backlog0=0.995, extra_bytes_median=3072)
IDENTITY = 0.999
S5_REQUIRED = ("V1", "V2", "V3", "V4", "V5", "V8", "V9", "V10")
CUE_KEYS = ("phase2", "phase3", "cues_degraded")
# S7's synthetic own player (the log keeps no players block): a fixed public deck, own hand visible, opponent hidden
S7_DECK = [26000000, 27000001, 26000002, 28000001, 28000000, 26000003, 26000014, 26000018]


def events(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(s) for s in h if s.strip()]


def verdict(ok, enough=True):
    return ("PASS" if ok else "FAIL") if enough else "SKIP"


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))] if xs else None


def live_rows(fr):
    """{generation: (side, x, y, card_id, hp, max_hp, behavior)} of one logged frame."""
    return {st[3]: (e[0], e[1], e[2], e[3], e[4], e[5], st[0]) for e, st in zip(fr["ents"], fr["ents_state"])}


def probe_rows(pf):
    return {e["category"]: (e["side"], e["x"], e["y"], e["card_id"], e["hp"], e["max_hp"], e["behavior_state_raw"])
            for e in pf["entities"]}


def cue_rows(p2, p3):
    """{generation: (buffs, attack)} from valid phase2/phase3 blocks; buffs as (type_id, name, remaining, total, source)."""
    buffs = {u["generation"]: tuple((b["type_id"], b["name"], b["remaining_ms_raw"], b["duration_ms_raw"],
                                     b["source_side_cached"]) for b in u["buffs"]) for u in p2["units"]}
    att = {b["generation"]: (json.dumps(b["attack"], sort_keys=True), b.get("null_reason")) for b in p3["bodies"]}
    return {g: (buffs.get(g), att.get(g)) for g in set(buffs) | set(att)}


def valid_cues(f):
    return bool(f.get("phase2") and f["phase2"].get("valid") and f.get("phase3") and f["phase3"].get("valid"))


def s1(a):
    sha_ok = bool(a.get("--sha-receipt")) and a.get("--sha-receipt") == a.get("--sha-device")
    return f"S1 {verdict(sha_ok and a.get('--build-checked', False))} device binary sha == receipt: {sha_ok}; " \
           f"game build checked by the lead: {bool(a.get('--build-checked'))}"


def s2(frames):
    us = [f["read_us"] for f in frames if f.get("read_us") is not None]
    deg = sum(1 for f in frames if f.get("cues_degraded"))
    bad = sum(1 for f in frames if not f.get("cues_degraded") and not valid_cues(f))
    gaps = [b["tick"] - a["tick"] for a, b in zip(frames, frames[1:])]
    g2 = sum(g == 2 for g in gaps) / len(gaps) if gaps else 0.0
    b0 = sum(f.get("backlog", 0) == 0 for f in frames) / len(frames) if frames else 0.0
    xb = [len(json.dumps([f.get("phase2"), f.get("phase3")], separators=(",", ":"))) for f in frames if valid_cues(f)]
    med, p95, xmed = (statistics.median(us) if us else None), pct(us, 0.95), (statistics.median(xb) if xb else None)
    ok = (us and med <= BUDGET["read_us_median"] and p95 <= BUDGET["read_us_p95"] and bad == 0 and g2 >= BUDGET["gap2"]
          and b0 >= BUDGET["backlog0"] and xmed is not None and xmed <= BUDGET["extra_bytes_median"])
    return (f"S2 {verdict(ok, bool(us))} read_us median {med} p95 {p95} (<= {BUDGET['read_us_median']} / "
            f"{BUDGET['read_us_p95']}); invalid cue frames {bad} (need 0); degraded frames {deg}; 2-tick gaps {g2:.4f} "
            f"(>= {BUDGET['gap2']}); backlog 0 {b0:.4f} (>= {BUDGET['backlog0']}); extra bytes median {xmed} p95 "
            f"{pct(xb, 0.95)} (<= {BUDGET['extra_bytes_median']}); frames {len(frames)}")


def s3_s4(frames, probe):
    pt = {}
    for pf in probe:
        if pf.get("battle_active") and pf.get("coherent"):
            pt[pf["game_tick"]] = pf
    n3 = same3 = n4 = same4 = 0
    diff3, diff4 = [], []
    for f in frames:
        pf = pt.get(f["tick"])
        if pf is None:
            continue
        a, b = live_rows(f), probe_rows(pf)
        for g in a.keys() & b.keys():
            n3 += 1
            same3 += a[g] == b[g]
            if a[g] != b[g] and len(diff3) < 5:
                diff3.append((f["tick"], g))
        if valid_cues(f) and pf.get("phase2", {}).get("valid") and pf.get("phase3", {}).get("valid"):
            c, d = cue_rows(f["phase2"], f["phase3"]), cue_rows(pf["phase2"], pf["phase3"])
            for g in c.keys() & d.keys():
                n4 += 1
                same4 += c[g] == d[g]
                if c[g] != d[g] and len(diff4) < 5:
                    diff4.append((f["tick"], g))
    r3, r4 = (same3 / n3 if n3 else 0.0), (same4 / n4 if n4 else 0.0)
    return [f"S3 {verdict(r3 >= IDENTITY, n3 >= 500)} v2 rows identical {same3}/{n3} = {r3:.5f} (need >= {IDENTITY}, "
            f">= 500 rows at shared ticks); first differences (tick, generation) {diff3}",
            f"S4 {verdict(r4 >= IDENTITY, n4 >= 500)} cue rows identical {same4}/{n4} = {r4:.5f} (need >= {IDENTITY}); "
            f"first differences {diff4}"]


def p3_frames(frames, defs_events):
    """The stream's frames in the raw shape validate_p3.load builds from (defs of every cues_defs event on the first)."""
    out = []
    for f in frames:
        if not valid_cues(f):
            continue
        ents = [dict(address=e[7], side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6],
                     behavior_state_raw=st[0], category=st[3]) for e, st in zip(f["ents"], f["ents_state"])]
        proj = [dict(side=p[0], x=p[1], y=p[2], card_id=p[3], generation_key=p[7], source=p[8], target=p[9])
                for p in f.get("proj") or ()]
        out.append(dict(game_tick=f["tick"], battle_active=True, read_us=f.get("read_us"), entities=ents,
                        projectiles=proj, effects=[dict(side=x[0]) for x in f.get("fx") or ()],
                        phase2=f["phase2"], phase3=dict(f["phase3"], defs=[])))
    if out:
        out[0]["phase3"]["defs"] = [d for e in defs_events for d in e["defs"]]
    return out


def s5(frames, defs_events):
    import validate_p3 as vp
    raw = p3_frames(frames, defs_events)
    lines = vp.run([vp.F(r) for r in raw], len(raw))
    tag = {ln.split()[0]: ln.split()[1] for ln in lines if ln[:1] == "V" and len(ln.split()) > 1}
    fails = [v for v in S5_REQUIRED if tag.get(v) == "FAIL"]
    skips = [v for v in S5_REQUIRED if tag.get(v) != "PASS" and v not in fails]
    head = f"S5 {verdict(not fails, bool(raw))} validate_p3 on the stream: required FAIL {fails}, not PASS (no data) {skips}"
    return [head] + ["   " + ln for ln in lines]


def s7(frames, n):
    from pipeline import live_mem
    picked = [f for f in frames if valid_cues(f)][:n]
    same = 0
    for f in picked:
        me = {"side": f["my_side"], "elixir_raw": int(round(f["elixir"] * 1e4)), "next_deck_index": 4,
              "hand_deck_indices": [0, 1, 2, 3], "cycle_deck_indices": [4, 5, 6, 7], "deck_card_ids": S7_DECK,
              "deck_form_flags": [0] * 8}
        opp = dict(me, side=1 - f["my_side"], hand_deck_indices=[-1] * 4, deck_card_ids=[], deck_form_flags=[])
        ents = [dict(address=e[7], side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6],
                     behavior_state_raw=st[0], category=st[3], evo=st[1], level=st[2])
                for e, st in zip(f["ents"], f["ents_state"])]
        base = dict(battle_active=True, coherent=True, game_tick=f["tick"], failure="none", players=[me, opp],
                    entities=ents)
        with_cues = dict(base, **{k: f.get(k) for k in CUE_KEYS})
        same += repr(live_mem.board_state(base)) == repr(live_mem.board_state(with_cues))
    return f"S7 {verdict(same == len(picked), bool(picked))} BoardState identical with / without the cue blocks: " \
           f"{same}/{len(picked)} frames"


def s8(log, path):
    ended = any(e["event"] == "end" for e in log)
    left = [s for s in Path(path).read_text().splitlines() if s.strip()] if path else None
    return f"S8 {verdict(ended and left == [], path is not None)} match ended: {ended}; reader processes left after " \
           f"the match: {'not given' if left is None else len(left)}"


def main(argv):
    flags = {"--build-checked"}
    a, pos, i = {}, [], 0
    while i < len(argv):
        if argv[i] in flags:
            a[argv[i]] = True
        elif argv[i].startswith("--"):
            a[argv[i]] = argv[i + 1]
            i += 1
        else:
            pos.append(argv[i])
        i += 1
    log = events(pos[0])
    frames = [e for e in log if e["event"] == "frame"]
    defs_events = [e for e in log if e["event"] == "cues_defs"]
    out = [s1(a), s2(frames)]
    out += s3_s4(frames, events(a["--probe"])) if a.get("--probe") else ["S3 SKIP no --probe", "S4 SKIP no --probe"]
    out += s5(frames, defs_events)
    out.append("S6 SKIP needs pipeline/live_unit_state.cues (spec section 5); compare by hand with validate_p3 V5/V6")
    out.append(s7(frames, int(a.get("--s7-frames", 400))))
    out.append(s8(log, a.get("--pgrep-after")))
    return out


if __name__ == "__main__":
    lines = main(sys.argv[1:])
    print("\n".join(lines))
    sys.exit(1 if any(ln.split()[1] == "FAIL" for ln in lines if ln[:1] == "S") else 0)
