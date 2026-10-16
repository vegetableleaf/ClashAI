"""Reader field validation for the owner's 10-16 classic battles (L74/parity/READER_VALIDATION_1016.md).

    python scratchpad/gauntlet/L74/parity/reader_val/validate_1016.py FRAME_LOG P2_FRAMES > out.txt
    (no args = match 1: live_play_20261016_115958 + p2_20261016T120616)

Reads ALREADY-DECODED JSON only: the live_play --log-frames log (B: ents / ents_state / proj / fx, t_dev, recording
segments) and the phase-2 capture (A: game_tick, sample_monotonic_us, entities, effects, phase2.units name / side /
buffs / ability). Bodies are keyed by generation id (B ents_state[3] == A entities.category == A phase2 generation);
runtime addresses are only an in-frame join key and are never printed. Opponent hand / next / elixir are never read.
Table radii below are SIM semantics from the 10-12 device tables (csv_logic: freeze.toml, tornado.toml,
rage_barbarian.toml), used only as a reference line in the output.
"""
from __future__ import annotations

import collections
import json
import math
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
B_LOG = REPO / "scratchpad/gauntlet/L68/live_reader/live_play_20261016_115958.jsonl"
A_LOG = REPO / "scratchpad/gauntlet/L70/reader/re_phase2/validation/p2_20261016T120616/frames.jsonl"
# effect card name -> (buff-name token, buff lands on 'enemy' or 'friendly' side, table radius in tiles or None)
FX_BUFF = {"Freeze": ("Freeze", "enemy", 3.0), "Tornado": ("Tornado", "enemy", 5.5),
           "RageBarbarian": ("Rage", "friendly", 3.0), "Rage": ("Rage", "friendly", 3.0),
           "IceWizard": ("IceWizardHero_Freeze", "enemy", None), "Tesla": ("Tesla_EV1", "enemy", None)}


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def runs(seq):
    """[(tick, value)] -> [[start_tick, end_tick, value]] runs of equal value."""
    out = []
    for t, v in seq:
        if out and out[-1][2] == v:
            out[-1][1] = t
        else:
            out.append([t, t, v])
    return out


def main(b_path=B_LOG, a_path=A_LOG) -> None:
    from pipeline.obs_contract import _catalog_names
    cat = _catalog_names()
    ev = [json.loads(line) for line in open(b_path, encoding="utf-8") if line.strip()]
    fb = [e for e in ev if e.get("event") == "frame"]
    segs = next((e["segments"] for e in ev if e.get("event") == "recording"), [])
    dry = next((e.get("dry_run") for e in ev if e.get("event") == "start"), None)
    fa = [json.loads(line) for line in open(a_path, encoding="utf-8") if line.strip()]
    fa = [f for f in fa if f.get("phase2")]
    own = fb[0]["my_side"]
    tdev = {f["tick"]: f["t_dev"] for f in fb}
    tks = sorted(tdev)

    def V(t: int) -> str:
        """Video time of tick t: raw screenrecord segment + seconds (segment start = device uptime before recording)."""
        if not segs:
            return "no video"
        td = tdev.get(t) or tdev[min(tks, key=lambda k: abs(k - t))]
        i = max((k for k, (_, t0) in enumerate(segs) if t0 <= td), default=0)
        s = td - segs[i][1]
        return f"seg{i} {int(s // 60)}:{s % 60:05.2f}"

    p2name, buffs_at, own_ab, opp_ab = {}, collections.defaultdict(dict), [], []
    for f in fa:
        for u in f["phase2"]["units"]:
            p2name[u["generation"]] = u["name"]
            buffs_at[f["game_tick"]][u["generation"]] = u["buffs"]
            ab = u.get("ability") or {}
            if ab.get("own_action"):
                own_ab.append((f["game_tick"], ab["own_action"]["state_raw"], ab["own_action"]["charges_raw"]))
            if ab and u["side"] != own:
                opp_ab.append((f["game_tick"], u["name"], ab.get("pending_on_body"), ab.get("cast_timer_ms_raw")))
    nm = lambda g, cid: p2name.get(g) or cat.get(cid, str(cid))  # noqa: E731

    # ---- [align]
    print(f"[align] observer side {own}; frame-log dry_run {dry}")
    amono = {f["game_tick"]: f["sample_monotonic_us"] / 1e6 for f in fa}
    common = sorted(set(tdev) & set(amono))
    dt = [amono[t] - tdev[t] for t in common]
    apos = {(f["game_tick"], e["category"]): (e["x"], e["y"], e["hp"]) for f in fa for e in f["entities"]}
    same = diff = 0
    for f in fb:
        for e, s in zip(f["ents"], f["ents_state"]):
            if (f["tick"], s[3]) in apos:
                ok = apos[(f["tick"], s[3])] == (e[1], e[2], e[4])
                same, diff = same + ok, diff + (not ok)
    print(f"  B frames {len(fb)} ticks {tks[0]}-{tks[-1]}; A frames {len(fa)} ticks {fa[0]['game_tick']}-{fa[-1]['game_tick']}"
          f" valid {sum(f['phase2']['valid'] for f in fa)} read_errors {sum(f['phase2']['read_errors'] for f in fa)}")
    if dt:
        print(f"  common ticks {len(common)}; A clock - B clock at the same tick: median {st.median(dt) * 1e3:.1f} ms, "
              f"min {min(dt) * 1e3:.1f}, max {max(dt) * 1e3:.1f}")
    print(f"  same body same tick: (x,y,hp) identical {same}, different {diff}")
    print(f"  video segments (device uptime at start): {[round(t0, 2) for _, t0 in segs]}")

    trk = collections.defaultdict(list)    # gen -> [(tick, side, x, y, hp, state, cid)]
    for f in fb:
        for e, s in zip(f["ents"], f["ents_state"]):
            trk[s[3]].append((f["tick"], e[0], e[1], e[2], e[4], s[0], e[3]))
    first_side = {g: tr[0][1] for g, tr in trk.items()}

    # ---- [state]
    print("\n[state] behavior_state_raw: steps and median speed (millitiles/tick) per body name")
    sp = collections.defaultdict(list)
    for g, tr in trk.items():
        for a, b in zip(tr, tr[1:]):
            if b[0] > a[0] and a[5] == b[5]:
                sp[(nm(g, a[6]), a[5])].append(dist(a[2:4], b[2:4]) / (b[0] - a[0]))
    for (n, s), v in sorted(sp.items()):
        print(f"  {n:30s} state {s:2d}: n {len(v):4d} median {st.median(v):6.1f}  still {sum(x < 1 for x in v) / len(v):.0%}")
    allst = collections.Counter(r[5] for tr in trk.values() for r in tr)
    print(f"  state census (all body-frames): {dict(sorted(allst.items()))}")
    for g, tr in trk.items():
        for t0, t1, s in runs([(r[0], r[5]) for r in tr]):
            if s not in (0, 1, 2, 4):
                r0, r1 = next(r for r in tr if r[0] == t0), next(r for r in tr if r[0] == t1)
                jb = sorted({b["name"] for t in range(t0 - 4, t1 + 5) for b in buffs_at.get(t, {}).get(g, [])})
                print(f"  rare state {s:2d} {nm(g, tr[0][6]):22s} side {r0[1]} {t0}-{t1} y {r0[3] / 1000:.1f}->"
                      f"{r1[3] / 1000:.1f} speed {dist(r0[2:4], r1[2:4]) / max(1, t1 - t0):.0f} buffs near {jb} video {V(t0)}")

    # ---- [tesla]
    print("\n[tesla] state runs; nearest enemy troop (tiles, centre to centre) at run start")
    for g, tr in trk.items():
        if not nm(g, tr[0][6]).startswith("Tesla"):
            continue
        print(f"  {nm(g, tr[0][6])} side {tr[0][1]} ticks {tr[0][0]}-{tr[-1][0]}")
        for t0, t1, s in runs([(r[0], r[5]) for r in tr]):
            f = next(x for x in fb if x["tick"] == t0)
            me = next(r for r in tr if r[0] == t0)
            en = [dist(me[2:4], e[1:3]) / 1000 for e in f["ents"] if e[0] != me[1] and e[3] != -1]
            print(f"    {t0}-{t1} state {s} nearest enemy {min(en) if en else float('nan'):.1f}  video {V(t0)}")

    # ---- [charge] speed bursts in state 1 (>= 1.6x the name's state-1 median), and what the run ended on
    print("\n[charge] state-1 speed bursts (>= 1.6x the card's state-1 median speed)")
    base = {n: st.median(v) for (n, s), v in sp.items() if s == 1}
    for g, tr in trk.items():
        n = nm(g, tr[0][6])
        if n not in base:
            continue
        burst, start_mv = [], None
        for a, b in zip(tr, tr[1:]):
            if a[5] != 1:
                start_mv = b
            v = dist(a[2:4], b[2:4]) / max(1, b[0] - a[0])
            if a[5] == b[5] == 1 and v >= 1.6 * base[n] and base[n] > 5:
                burst.append((b[0], v, b, start_mv))
        groups, cur = [], []
        for x in burst:
            if cur and x[0] - cur[-1][0] > 4:
                groups.append(cur)
                cur = []
            cur.append(x)
        groups += [cur] if cur else []
        for grp in groups:
            t0, t1 = grp[0][0], grp[-1][0]
            pre = dist(grp[0][3][2:4], grp[0][2][2:4]) / 1000 if grp[0][3] else float("nan")
            after = [r for r in tr if r[0] > t1][:3]
            end = after[0] if after else None
            hit = []
            if end:
                for f in fb:
                    if t1 - 2 <= f["tick"] <= t1 + 8:
                        for e, s in zip(f["ents"], f["ents_state"]):
                            if e[0] != tr[0][1] and dist(e[1:3], end[2:4]) < 4000:
                                hit.append((s[3], f["tick"], e[4], nm(s[3], e[3])))
            drops = []
            for gg in {h[0] for h in hit}:
                hs = sorted((h[1], h[2], h[3]) for h in hit if h[0] == gg)
                last_seen = trk[gg][-1][0]
                drops.append(f"{hs[0][2]}: hp {hs[0][1]}->{hs[-1][1]}" + (f" (gone after {last_seen})" if last_seen <= t1 + 8 else ""))
            print(f"  {n} side {tr[0][1]} gen {g}: burst ticks {t0}-{t1} ({len(grp)} steps) speed median "
                  f"{st.median(x[1] for x in grp):.0f} vs base {base[n]:.0f}; moved {pre:.1f} tiles in state 1 before the "
                  f"burst; next state {end[5] if end else '-'} at {end[0] if end else '-'}; enemies within 4 tiles: "
                  f"{drops}; video {V(t0)} -> {V(t1)}")

    # ---- [proj]
    print("\n[proj] per card: rows, distinct shots, source resolved, target resolved, target point vs target body")
    agg = collections.defaultdict(collections.Counter)
    tgt_err, shots, firsts = collections.defaultdict(list), collections.defaultdict(set), {}
    together = []                          # frames with X-Bow and IW shots in flight at once: (tick, xbow tgts, iw tgts)
    for f in fb:
        a2 = {e[7]: (e, s) for e, s in zip(f["ents"], f["ents_state"])}
        inflight = collections.defaultdict(set)
        for p in f["proj"]:
            side, x, y, cid, tx, ty, addr, gk, src, tgt = p
            key = (side, cat.get(cid, "tower/king" if cid == -1 else str(cid)))
            c = agg[key]
            c["rows"] += 1
            shots[key].add(gk)
            sname = nm(a2[src][1][3], a2[src][0][3]) if src in a2 else None
            if sname:
                c["src_body"] += 1
                c["src_" + sname] += 1
            if tgt in a2:
                te, ts = a2[tgt]
                c["tgt_body"] += 1
                c["tgt_enemy"] += te[0] != side
                tgt_err[key].append(dist((tx, ty), te[1:3]))
                if gk not in firsts:
                    firsts[gk] = (f["tick"], sname, ts[3], nm(ts[3], te[3]))
                inflight[sname].add(nm(ts[3], te[3]) + f"#{ts[3] % 1000}")
            elif tgt is None:
                c["tgt_null"] += 1
        if inflight.get("Xbow") and inflight.get("IceWizardHero"):
            together.append((f["tick"], inflight["Xbow"], inflight["IceWizardHero"]))
    for k, c in sorted(agg.items(), key=str):
        e = tgt_err.get(k)
        srcs = {kk[4:]: v for kk, v in c.items() if kk.startswith("src_") and kk != "src_body"}
        print(f"  side {k[0]} {k[1]:13s} rows {c['rows']:4d} shots {len(shots[k]):3d} | src body {c['src_body']:4d} {srcs} | "
              f"tgt body {c['tgt_body']:4d} enemy {c['tgt_enemy']:4d} null {c['tgt_null']:4d} | point-vs-body median "
              f"{(st.median(e) / 1000 if e else float('nan')):.2f} tiles")
    xs = [v for v in firsts.values() if v[1] == "Xbow"]
    iw = [v for v in firsts.values() if v[1] == "IceWizardHero"]
    pairs = [(a, b) for a in xs for b in iw if abs(a[0] - b[0]) <= 20]
    diffp = [(a, b) for a, b in pairs if a[2] != b[2]]
    print(f"  X-Bow shots {len(xs)}, IceWizardHero shots {len(iw)}; pairs fired within 1 s: {len(pairs)}, different "
          f"target {len(diffp)}")
    for a, b in diffp[:6]:
        print(f"    tick {a[0]} X-Bow -> {a[3]} | tick {b[0]} IW -> {b[3]}  video {V(a[0])}")
    split = [x for x in together if not x[1] & x[2]]
    print(f"  frames with X-Bow and IW shots in flight together: {len(together)}, disjoint targets {len(split)}")
    for t, xb, iwt in split[:8]:
        print(f"    tick {t} X-Bow -> {sorted(xb)} | IW -> {sorted(iwt)}  video {V(t)}")

    # ---- [fx] effects, checked against buffs inside capture A (same frame)
    print("\n[fx] effects: life, remaining_ms, and same-frame buffs on bodies (capture A)")
    inst = collections.defaultdict(list)
    for f in fb:
        for x in f["fx"]:
            inst[(x[0], x[3], x[7])].append((f["tick"], x[1], x[2], x[4], x[5]))
    afx = collections.defaultdict(list)
    for f in fa:
        for x in f["effects"]:
            afx[x["generation_key"]].append(f)
    for (side, cid, gk), rows in sorted(inst.items(), key=lambda kv: kv[1][0][0]):
        dec = collections.Counter((b[3] - a[3]) / (b[0] - a[0]) for a, b in zip(rows, rows[1:]) if b[0] > a[0])
        cn = cat.get(cid, str(cid))
        print(f"  side {side} {cn:14s} ticks {rows[0][0]}-{rows[-1][0]} ({len(rows)} frames) at ({rows[0][1] / 1000:.1f},"
              f"{rows[0][2] / 1000:.1f}) moved {max(dist(rows[0][1:3], r[1:3]) for r in rows) / 1000:.1f} | remaining "
              f"{rows[0][3]}->{rows[-1][3]} dec/tick {dec.most_common(2)} level {rows[0][4]} | video {V(rows[0][0])}")
        if cn not in FX_BUFF or gk not in afx:
            continue
        tok, who, rad = FX_BUFF[cn]
        tgt_side = side if who == "friendly" else 1 - side
        inb, outb, wrong = [], [], 0
        for f in afx[gk]:
            fx = next(x for x in f["effects"] if x["generation_key"] == gk)
            for e in f["entities"]:
                bl = [b["name"] for b in buffs_at[f["game_tick"]].get(e["category"], []) if tok in b["name"]]
                d = dist((fx["x"], fx["y"]), (e["x"], e["y"])) / 1000
                if e["side"] != tgt_side:
                    wrong += bool(bl)
                    continue
                (inb if bl else outb).append((d, nm(e["category"], e["card_id"])))
        print(f"      target side {tgt_side}: with '{tok}*' buff {len(inb)} body-frames (max dist "
              f"{max((d for d, _ in inb), default=float('nan')):.2f}), without {len(outb)} (min dist "
              f"{min((d for d, _ in outb), default=float('nan')):.2f}; within table radius {rad}: "
              f"{sum(d <= (rad or 0) for d, _ in outb)}); buffed bodies {dict(collections.Counter(n for _, n in inb))};"
              f" wrong-side buffed {wrong}")

    # ---- [buffs]
    print("\n[buffs] capture A: per name rows, instances, bodies, decrement/tick, first remaining/duration, source side")
    bt = collections.defaultdict(list)
    for f in fa:
        for u in f["phase2"]["units"]:
            for b in u["buffs"]:
                bt[(b["name"], u["generation"], b["address"])].append(
                    (f["game_tick"], b["remaining_ms_raw"], b["duration_ms_raw"], b["source_side_cached"], u["side"], b["config"]))
    byname = collections.defaultdict(lambda: dict(rows=0, bodies=set(), dec=collections.Counter(), first=[], src=set(),
                                                  flags=set(), on=collections.Counter(), ticks=[]))
    for (n, g, _), rows in bt.items():
        d = byname[n]
        d["rows"] += len(rows)
        d["bodies"].add(g)
        d["on"][p2name.get(g)] += 1
        d["first"].append((rows[0][1], rows[0][2]))
        d["ticks"].append(rows[0][0])
        d["src"].add((rows[0][3], rows[0][4]))
        d["flags"] |= {k for k, v in rows[0][5].items() if v and k in ("Invisible", "Clone", "Shield")}
        for a, b in zip(rows, rows[1:]):
            if b[0] > a[0] and b[1] <= a[1]:
                d["dec"][(a[1] - b[1]) / (b[0] - a[0])] += 1
    for n, d in sorted(byname.items()):
        print(f"  {n:34s} rows {d['rows']:4d} inst {len(d['first']):3d} bodies {len(d['bodies']):3d} (src,body side) "
              f"{sorted(d['src'])} flags {sorted(d['flags'])} dec {d['dec'].most_common(2)} first rem/dur "
              f"{collections.Counter(d['first']).most_common(3)} on {dict(d['on'])} first ticks {sorted(d['ticks'])[:6]} "
              f"video {V(min(d['ticks']))}")
    inv = sum(1 for f in fa for u in f["phase2"]["units"] for b in u["buffs"] if b["config"].get("Invisible"))
    print(f"  buff rows with Invisible flag: {inv}")

    # ---- [ability]
    print("\n[ability] own hero ability state runs (state, charges); opponent hero indicators")
    for t0, t1, v in runs([(t, (s, c)) for t, s, c in own_ab]):
        print(f"  own {t0}-{t1} state {v[0]} charges {v[1]}  video {V(t0)}")
    hero = collections.Counter((n, p, c) for _, n, p, c in opp_ab)
    print(f"  opponent hero bodies (name, pending_on_body, cast_timer_ms_raw): {dict(hero)}")
    s10 = [(r[0], nm(g, r[6]), r[1]) for g, tr in trk.items() for r in tr if r[5] == 10]
    print(f"  behavior_state_raw == 10 frames: {len(s10)} {s10[:12]}")

    # ---- [events]
    print("\n[events] first frame of each new body (not swarm members) / spell projectile / effect, with video time")
    seen = set()
    for f in fb:
        for e, s in zip(f["ents"], f["ents_state"]):
            if s[3] not in seen and e[3] != -1:
                seen.add(s[3])
                n = nm(s[3], e[3])
                if not any(w in n for w in ("Skeleton", "FireSpirits", "Floating", "Spirit", "Goblin", "Bat")):
                    print(f"  {f['tick']:5d} side {e[0]} body {n:26s} at ({e[1] / 1000:.1f},{e[2] / 1000:.1f}) video {V(f['tick'])}")
        for p in f["proj"]:
            if 28000000 <= p[3] < 29000000 and ("p", p[7]) not in seen:
                seen.add(("p", p[7]))
                print(f"  {f['tick']:5d} side {p[0]} spell {cat.get(p[3]):10s} at ({p[1] / 1000:.1f},{p[2] / 1000:.1f}) -> "
                      f"({p[4] / 1000:.1f},{p[5] / 1000:.1f}) video {V(f['tick'])}")
        for x in f["fx"]:
            if ("f", x[7]) not in seen:
                seen.add(("f", x[7]))
                print(f"  {f['tick']:5d} side {x[0]} effect {cat.get(x[3]):10s} at ({x[1] / 1000:.1f},{x[2] / 1000:.1f}) "
                      f"rem {x[4]} video {V(f['tick'])}")
    gone = [(g, tr[-1][0], nm(g, tr[-1][6])) for g, tr in trk.items() if first_side[g] != own and tr[-1][6] == -1
            and tr[-1][0] < tks[-1]]
    print(f"  enemy towers destroyed (last tick): {gone}")


if __name__ == "__main__":
    main(*(Path(p) for p in sys.argv[1:3]))
