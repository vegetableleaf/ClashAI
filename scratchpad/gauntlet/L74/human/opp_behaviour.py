"""How un-human are the SIM opponents?  Opponent play behaviour, LIVE 12k humans vs SIM opponents, per archetype (owner plan 10-15).

ONE detector for both sources: pipeline.opp_elixir_count.PlayDetector (the exact code the live pilot's opponent counter runs)
turns 10-tick frames of opponent bodies into plays (tick, card, cost, birth centroid).  Same blind spots on both sides:
bodiless spells (log, zap, arrows, fireball, rocket, tornado, ...) are invisible; a re-play of a card within 100 ticks merges.
  live: decision events' public.raw_bodies (~every 10 ticks) of the listed icebow main-account logs
  SIM : matches.jsonl rows with behaviour.lr_frames / lr_plays / lr_dec (scratchpad/gauntlet/L74/loss_review/econ_sim_patch.py
        telemetry: econ_r1_pod.sh, calib_opp_pod.sh, opp_behaviour_pod.sh).  lr_plays also gives the EXACT opponent plays, kept only
        to measure the detector's recall (a SIM-only ground truth) -- never used for the features.
Coordinates: OUR frame in tiles (our king (9,3), y grows toward their side, river y=16).

    python opp_behaviour.py live                       -> data/live.json.gz
    python opp_behaviour.py sim NAME DIR_OR_JSONL ...  -> data/sim_NAME.json.gz   (DIR is searched for matches.jsonl)
    python opp_behaviour.py report [--sim NAME ...]    -> BEHAVIOUR.md  (first --sim is the primary comparison)
"""
from __future__ import annotations
import argparse, collections, glob, gzip, json, math, os, re, sys
from pathlib import Path

try:
    import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # below normal
except Exception:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "scratchpad/gauntlet/L74/weekend")]
import archetypes as A                                                    # noqa: E402  (weekend/archetypes.py)
from pipeline import vocab                                                # noqa: E402
from pipeline.obs_contract import catalog_card_form                       # noqa: E402
from pipeline.opp_elixir_count import PlayDetector                        # noqa: E402

DATA = HERE / "data"
LOGS = ROOT / "scratchpad/gauntlet/L68/live_reader"
LIVE_LIST = ROOT / "scratchpad/gauntlet/L74/mix/live_cost_1001.json"      # [log_file, result, seen_cards]
CATALOG = ROOT / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json"
TPS, WIN = 20, 160                                                          # ticks per second; 8 s push window
RIVER, BRIDGE_R = 16.0, 3.0
CLEAN_GAP = 12                                                              # ticks; frames are 10 apart, live reader gaps reach 30-40
FEATS = ("ppm_1x", "ppm_2x", "own_half", "bridge", "our_half", "first_tick", "react_s", "react_3s", "react_lift", "push_mean", "push_max",
         "spell_share", "opp_el")
SIGS = ("megaknight", "hogrider", "golem", "firecracker", "minipekka", "elixirgolem", "royalrecruits", "skeletonballoon")

# what the on-disk SIM sets are (run.json of each chunk): opponent checkpoint and sampling temperature; learner r1 / D3 in all
LABEL = {"ECON_r1": "E4 opp, T 0.1 (the SIM default; 960 games)", "CALIB_e4_T03": "E4 opp, T 0.03", "CALIB_gen1_T30": "gen_v1_s0 opp, T 0.3",
         "CALIB_old_T10": "rdef r3c opp, T 0.1", "CALIB_r1_T03": "r1 as opp, T 0.03", "CALIB_r1_T10": "r1 as opp, T 0.1"}
_CAT = None
def catalog():
    """engine key -> (type, elixir); display name -> base card_id.  The cost/spell table for BOTH sources."""
    global _CAT
    if _CAT is None:
        cards = json.loads(CATALOG.read_text(encoding="utf-8"))["cards"]
        _CAT = ({vocab.engine_key(c["display_name"]): (c["type"], float(c["elixir"])) for c in cards},
                {re.sub(r"[^a-z0-9]", "", c["display_name"].lower()): int(c["card_id"]) for c in cards})
    return _CAT


def own(side, x, y):
    return ((18000 - x) / 1000.0, (32000 - y) / 1000.0) if side == 1 else (x / 1000.0, y / 1000.0)


def plays_of(frames, my_side):
    """[(game_tick, entities)] -> opponent plays [tick, key, cost, x, y, n_bodies, frame gap] in OUR tile frame (PlayDetector verbatim)."""
    det, evs, out = PlayDetector(), [], []
    det.my_side = my_side
    prev, gap = None, {}                                         # tick -> ticks since the previous frame (a reader gap moves a unit before it is seen)
    for t, ents in frames:
        gap[t] = t - prev if prev is not None else 0; prev = t
        evs += det.feed({"game_tick": t, "entities": ents})
    for ev in evs:                                               # after the loop: n_bodies grows as later swarm bodies join
        c = ev.cost if ev.cost is not None else (catalog()[0].get(ev.key) or (None, None))[1]
        x, y = own(my_side, ev.x, ev.y)
        out.append([ev.tick, ev.key, c, round(x, 2), round(y, 2), ev.n_bodies, gap[ev.tick]])
    return out


def pre_est(plays, est):
    """Append (index 7) the public counter reading at the last decision strictly before each play (a +26-tick forecast, live and SIM alike)."""
    ts = [e[0] for e in est]
    import bisect
    for p in plays:
        k = bisect.bisect_left(ts, p[0]) - 1
        p.append(est[k][1] if k >= 0 else None)
    return plays


# ------------------------------------------------------------------ extraction
def extract_live(path, seen, res):
    frames, est, mine, side = [], [], [], None
    with open(path, encoding="utf8", errors="replace") as fh:
        for l in fh:
            if l.startswith('{"event": "decision"'):
                d = json.loads(l); p = d.get("public") or {}
                if "observer_side" not in p or "raw_bodies" not in p:
                    continue
                side = p["observer_side"]; t = int(d["tick"])
                frames.append((t, p["raw_bodies"]))
                if p.get("opponent_elixir_estimate") is not None:
                    est.append((t, float(p["opponent_elixir_estimate"])))
            elif l.startswith('{"event": "play"'):
                mine.append(int(json.loads(l)["tick"]))
    if side is None or len(frames) < 20:
        return None
    return dict(src="live", id=os.path.basename(path), seen=seen, res=res, end=frames[-1][0], t0=frames[0][0], side=side,
                plays=pre_est(plays_of(frames, side), est), mine=mine)


def sim_ids():
    """normalised card name -> base card_id for SIM body names (RoyaleAPI keys like 'inferno-dragon')."""
    ids = dict(catalog()[1])
    # RoyaleAPI key -> catalog display name (econ2.ALIAS + the pairs found by listing the unmapped names of the 10-14 SIM runs)
    for k, v in {"cannoncart": "movingcannon", "zappies": "minisparkys", "firespirit": "firespirits", "icespirit": "icespirits", "bandit": "assassin",
                 "royalghost": "ghost", "barbarianbarrel": "barblog", "elitebarbarians": "angrybarbarians", "healspirit": "heal",
                 "icegolem": "icegolemite", "sparky": "zapmachine", "magicarcher": "elitearcher", "flyingmachine": "dartbarrell",
                 "skeletonbarrel": "skeletonballoon", "dartgoblin": "blowdartgoblin", "archers": "archer", "nightwitch": "darkwitch",
                 "lumberjack": "axeman", "furnace": "firespirithut", "motherwitch": "witchmother", "runegiant": "giantbuffer",
                 "guards": "skeletonwarriors", "executioner": "darkmagic"}.items():
        ids.setdefault(k, ids.get(v))
    return {k: v for k, v in ids.items() if v}


def extract_sim(r, ids, unmapped):
    b = r.get("behaviour") or {}
    if "lr_frames" not in b or "lr_dec" not in r:
        return None
    side = int(r["learner_side"]); opp = 1 - side
    frames, maxhp = [], {}
    for t, _el, bodies, _tw in b["lr_frames"]:
        ents = []
        for c, x, y, hp, i in bodies:
            cid = ids.get(re.sub(r"[^a-z0-9]", "", c.lower()))
            if cid is None:
                unmapped[c] += 1; continue
            maxhp[i] = max(maxhp.get(i, 0), hp or 0)         # lr_frames carry current hp only: first sight = fresh = max
            ents.append(dict(side=opp, x=x, y=y, card_id=cid, max_hp=maxhp[i], address=i))
        frames.append((int(t), ents))
    seen = sorted({A.canon(catalog_card_form(e["card_id"])[0]) for _, es in frames[::10] for e in es if catalog_card_form(e["card_id"])[0]})
    est = [(int(d[0]), float(d[6])) for d in r["lr_dec"] if d[6] is not None]
    plays = pre_est(plays_of(frames, side), est)
    truth = [[int(t), vocab.engine_key(c), el] for t, s, c, el, ab in b["lr_plays"] if s == opp and not ab]
    for q in truth:                                             # detector recall vs the exact plays
        q.append(any(p[1] == q[1] and q[0] - 10 <= p[0] <= q[0] + 60 for p in plays))
    return dict(src="sim", id=r.get("tag"), seen=seen, res=1 if r.get("outcome") == "win" else 0, end=int(r["end_tick"]),
                t0=frames[0][0] if frames else 0, side=side, plays=plays, truth=truth, deck=r.get("opp_deck"),
                mine=[int(t) - 26 for t, s, c, el, ab in b["lr_plays"] if s == side and not ab])


def save(name, ms):
    DATA.mkdir(exist_ok=True)
    with gzip.open(DATA / f"{name}.json.gz", "wt") as fh:
        json.dump(ms, fh)
    print("saved", name, len(ms), flush=True)


def load(name):
    with gzip.open(DATA / f"{name}.json.gz", "rt") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ features
NAN = float("nan")


def features(m):
    """Per-match opponent behaviour features from m['plays'] (+ m['mine'], m['end'], m['t0'])."""
    P, end, t0 = m["plays"], m["end"], m["t0"]
    f = dict.fromkeys(FEATS, NAN)
    d1, d2 = min(end, 2400) - t0, end - 2400                    # exposure in ticks: 1x, then 2x + overtime
    n1 = sum(p[0] < 2400 for p in P); n2 = len(P) - n1
    if d1 >= 600: f["ppm_1x"] = n1 / (d1 / (60.0 * TPS))
    if d2 >= 600: f["ppm_2x"] = n2 / (d2 / (60.0 * TPS))
    if P:
        n = len(P)
        C = [p for p in P if p[6] <= CLEAN_GAP]                   # position shares: first sighting <= 1 frame after the deploy only
        if C:
            f["bridge"] = sum(abs(p[4] - RIVER) <= BRIDGE_R for p in C) / len(C)
            f["own_half"] = sum(p[4] > RIVER + BRIDGE_R for p in C) / len(C)
            f["our_half"] = sum(p[4] < RIVER - BRIDGE_R for p in C) / len(C)
        f["first_tick"] = P[0][0]
        f["spell_share"] = sum((catalog()[0].get(p[1]) or ("",))[0] == "spell" for p in P) / n
        pe = [p[7] for p in P if p[7] is not None]
        if pe: f["opp_el"] = sum(pe) / len(pe)
    if m["mine"]:
        ts = [p[0] for p in P]; gaps = []
        for o in m["mine"]:
            nxt = next((t for t in ts if t > o), None)
            gaps.append(min(10.0, (nxt - o) / TPS) if nxt is not None else 10.0)   # no answer within the cap counts as the cap
        f["react_s"] = sum(gaps) / len(gaps); f["react_3s"] = sum(g <= 3.0 for g in gaps) / len(gaps)
        # chance level of react_3s: the share of the match in which SOME play of theirs starts within the next 3 s (union of [t-60, t))
        cov, hi = 0, t0
        for t in ts:
            lo = max(t - 3 * TPS, hi, t0); cov += max(0, t - lo); hi = max(hi, t)
        f["react_lift"] = f["react_3s"] - cov / max(1, end - t0)
    nw = int((end - t0) // WIN)
    if nw >= 3:
        w = [0.0] * nw
        for p in P:
            k = int((p[0] - t0) // WIN)
            if 0 <= k < nw: w[k] += p[2] or 0.0
        f["push_mean"], f["push_max"] = sum(w) / nw, max(w)
    return f


def groups_of(m):
    """Group names a match belongs to: ALL, its archetype, and every signature card it showed."""
    s = set(m["seen"])
    return ["ALL", "arch:" + A.classify(s)] + ["sig:" + c for c in SIGS if c in s]


def stats(vals):
    v = [x for x in vals if not math.isnan(x)]
    if len(v) < 2: return len(v), (sum(v) / len(v) if v else NAN), NAN
    mu = sum(v) / len(v)
    return len(v), mu, math.sqrt(sum((x - mu) ** 2 for x in v) / (len(v) - 1))


def compare(L, S):
    """L, S: lists of feature dicts.  -> {feat: (nL, muL, nS, muS, d)} (d = (muS - muL) / pooled SD, Cohen)."""
    out = {}
    for k in FEATS:
        nl, ml, sl = stats([x[k] for x in L]); ns, ms, ss = stats([x[k] for x in S])
        d = NAN
        if nl >= 5 and ns >= 5:
            sp = math.sqrt(((nl - 1) * sl ** 2 + (ns - 1) * ss ** 2) / (nl + ns - 2))
            d = (ms - ml) / sp if sp > 0 else NAN
        out[k] = (nl, ml, ns, ms, d)
    return out


def distance(cmp, nl, ns):
    """RMS effect size over the features, and the value it would have from sampling noise alone (matches differ by chance)."""
    ds = [c[4] for c in cmp.values() if not math.isnan(c[4])]
    if not ds: return NAN, NAN
    return math.sqrt(sum(d * d for d in ds) / len(ds)), math.sqrt(1.0 / nl + 1.0 / ns)


# ------------------------------------------------------------------ report
NOTES = """## 5. Concerns (read before trusting a number)

- **Detection is shared, not exact.** Both sources go through the live PlayDetector, so the features are comparable, but bodiless spells are invisible
  (SIM: only 27.6% of spell plays are found; 97.5% of non-spell plays), same-card re-plays within 100 ticks merge, and plays are positioned at the
  FIRST SIGHTING.  22.5% of live plays are first seen > 12 ticks after the previous frame (SIM: 0%); the unit has already walked, so those are left out
  of the position shares.  Measured: non-barrel plays on our half are 10.2% for those gappy live sightings, 6.3% for clean live sightings, 1.4% in SIM -- the
  gap explains only part of the live-SIM `our_half` difference (the rest is humans dropping troops on our side: pocket / jump placements, untested which).
  Human spell use is therefore UNMEASURED here (live `spell_share` counts only graveyard / barrels / delivery). Goblin Barrel and Graveyard are ~100%
  `our_half` by design, so `our_half` is mostly the barrel share.
- **Different learner.** Live = icebow (r1e / r1 variants, anti-leak on some logs); SIM = r1 under the D3 stack. `react_*` measures THEIR play after OUR
  play, so it carries our timing and our play rate; `react_lift` removes only the opponent's own play rate. Live tap ticks are decision ticks (the real tap
  and card landing are later), SIM tap = deploy - 26.
- **Different deck mix.** SIM = the CAL set c pool (cal_evo / cal_lad), not the live-mirrored pool; `ALL` is mix-confounded and archetypes are
  classified from CARDS SEEN (live: every 10th decision; SIM: every 10th 10-tick frame), not the full deck. Small groups: royal_giant_monk (7 SIM), pekka_bridge
  (19), royalrecruits (22), elixirgolem (23), royal_giant (28), firecracker (35), megaknight (37): their distance has a large floor (column) and is
  near the noise at n < 15.
- **`opp_el` is counter vs counter** (see section 4). It drifts up with invisible spells, so a lower SIM value does not mean SIM opponents spend more.
- **The distance is an RMS of 13 correlated features** (ppm_1x / ppm_2x, react_s / react_3s / react_lift, push_mean / push_max are not independent):
  use it to rank archetypes, not as a calibrated number. Effect sizes are per MATCH, not per play.
- **Frames.** Decision events only (median 10 ticks, max ~44); the 2-tick `frame` events of the 176 logs since 10-15 are not used so every log
  is read the same way. Live `end` = last decision tick; matches that end before 2:00 have no `ppm_2x`.

## 6. SIM status and the pod command

On disk (no new SIM run needed): `pod_backup_weekend/pod1014b_econ/ECON_r1` (960 games, r1 D3 vs E4 T .1, CAL pool; the patched telemetry `lr_frames` /
`lr_plays` / `lr_dec`) plus the five `pod1014b_calib/CALIB` sets (480 each; section 3). Extract with
`python opp_behaviour.py sim NAME DIR ...`. The standard SIM output (`behaviour` without the econ_sim_patch telemetry) does NOT carry the opponent's
plays or bodies, so a fresh SIM run needs the isolated patched copy; `opp_behaviour_pod.sh` does exactly that for the LIVE-MIRRORED pool:

    nohup bash scratchpad/gauntlet/L74/human/opp_behaviour_pod.sh > /workspace/oppbeh.log 2>&1 &
    # = gap.py --arms D3 --seed-start 741200 / 742000 --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --opp-T .1, 13 workers,
    #   then opp_behaviour.py sim LIVEPOOL_r1 -> results/OPPBEH_LIVEPOOL_r1/sim_LIVEPOOL_r1.json.gz
    # copy it to scratchpad/gauntlet/L74/human/data/ and: python opp_behaviour.py report --sim LIVEPOOL_r1 ECON_r1

The pod script is UNRUN (the telemetry path itself is proven on the 10-14 data above; the new `--census-file` combination has not been
run with the patch).
"""

def fmt(x, p=2):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{p}f}"


def report(live, sims, out):
    name0, S0 = sims[0]
    fl = [(m, features(m)) for m in live]
    L = ["# Opponent behaviour: SIM opponents vs real 12k humans", "",
         f"LIVE: {len(live)} icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  ",
         f"SIM (primary): `{name0}`, {len(S0)} matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; "
         "distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME "
         "population give by chance (distance <= ~1.5 x floor = indistinguishable).", "",
         "Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; "
         "`own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); "
         "`first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share "
         "of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` "
         "share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir "
         "counter at the last decision before the play (a +26-tick forecast on both sources).", ""]
    sm = {}
    for nm, ms in sims:
        sm[nm] = [(m, features(m)) for m in ms]
    g = collections.OrderedDict()
    for m, f in fl:
        for k in groups_of(m): g.setdefault(k, ([], []))[0].append(f)
    for m, f in sm[name0]:
        for k in groups_of(m): g.setdefault(k, ([], []))[1].append(f)
    rows = []
    for k, (a, b) in g.items():
        if len(a) >= 5 and len(b) >= 5:
            c = compare(a, b); dist, floor = distance(c, len(a), len(b)); rows.append((k, len(a), len(b), dist, floor, c))
    rows.sort(key=lambda r: (r[0] != "ALL", not r[0].startswith("arch:"), -r[3]))
    top = next((r for r in rows if r[0] == "ALL"), None)
    if top:
        big = sorted(((abs(c[4]), x, c) for x, c in top[5].items() if not math.isnan(c[4])), reverse=True)[:4]
        L += ["**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps " + "; ".join(
            f"`{x}` live {fmt(c[1], 2)} vs SIM {fmt(c[3], 2)} (d {c[4]:+.2f})" for _, x, c in big) + ".", ""]
    L += [f"## 1. Distance per archetype (primary SIM: {name0})", "",
          "| group | n live | n SIM | distance | floor | " + " | ".join(FEATS) + " |", "|---|---:|---:|---:|---:|" + "---:|" * len(FEATS)]
    for k, nl, ns, dist, floor, c in rows:
        flag = " (small n)" if min(nl, ns) < 15 else ""
        L.append(f"| {k}{flag} | {nl} | {ns} | **{fmt(dist)}** | {fmt(floor)} | " + " | ".join(fmt(c[x][4]) for x in FEATS) + " |")
    skipped = [(k, len(a), len(b)) for k, (a, b) in g.items() if min(len(a), len(b)) < 5]
    if skipped: L += ["", "Groups with n < 5 on a side (no comparison): " + ", ".join(f"{k} (live {a}, SIM {b})" for k, a, b in skipped)]
    L += ["", "## 2. Feature means, live vs SIM, per group", ""]
    for k, nl, ns, dist, floor, c in rows:
        L += [f"### {k}  (live n={nl}, SIM n={ns}, distance {fmt(dist)}, floor {fmt(floor)})", "",
              "| feature | live mean | SIM mean | d |", "|---|---:|---:|---:|"]
        for x in FEATS:
            n1, m1, n2, m2, d = c[x]
            p = 3 if x in ("own_half", "bridge", "our_half", "react_3s", "spell_share") else 2
            L.append(f"| {x} | {fmt(m1, p)} (n {n1}) | {fmt(m2, p)} (n {n2}) | {fmt(d)} |")
        L.append("")
    if len(sims) > 1:                                                     # other SIM opponent policies, overall only
        L += ["## 3. Other SIM opponent policies, ALL archetypes (their deck mixes differ from live; read the distance as a ranking only)", "",
              "| SIM set | n | distance | floor | " + " | ".join(FEATS) + " |", "|---|---:|---:|---:|" + "---:|" * (len(FEATS) + 1)]
        for nm, ms in sims:
            fs = [f for _, f in sm[nm]]; c = compare([f for _, f in fl], fs); dist, floor = distance(c, len(fl), len(fs))
            L.append(f"| {LABEL.get(nm, nm)} | {len(fs)} | **{fmt(dist)}** | {fmt(floor)} | " + " | ".join(fmt(c[x][4]) for x in FEATS) + " |")
        L.append("")
    tr = [q for m, _ in sm[name0] for q in m.get("truth", [])]
    if tr:
        sp = [q for q in tr if (catalog()[0].get(q[1]) or ("",))[0] == "spell"]
        ns = [q for q in tr if q not in sp]
        el = [q[2] for q in tr if q[2] is not None]
        pe = [p[7] for m, _ in sm[name0] for p in m["plays"] if p[7] is not None]
        L += ["## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)", "",
              f"- exact opponent plays {len(tr)}; the detector (live code) finds {sum(q[3] for q in tr)} = {100*sum(q[3] for q in tr)/len(tr):.1f}%",
              f"- non-spell plays: {sum(q[3] for q in ns)}/{len(ns)} = {100*sum(q[3] for q in ns)/max(1,len(ns)):.1f}% found",
              f"- spell plays: {sum(q[3] for q in sp)}/{len(sp)} = {100*sum(q[3] for q in sp)/max(1,len(sp)):.1f}% found "
              f"({100*len(sp)/len(tr):.1f}% of all SIM plays are spells; live sees only the body-dropping ones)",
              f"- SIM opponent elixir at play: true {fmt(sum(el)/len(el))} (mean, exact) vs the public counter {fmt(sum(pe)/len(pe))} (last decision before the play). "
              "The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is "
              "+0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every "
              "invisible spell the opponent casts (SIM opponents cast many).", ""]
    Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote", out)
    return rows


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("live")
    s = sub.add_parser("sim"); s.add_argument("name"); s.add_argument("paths", nargs="+")
    r = sub.add_parser("report"); r.add_argument("--sim", nargs="+", default=["ECON_r1"]); r.add_argument("--out", default=str(HERE / "BEHAVIOUR.md"))
    a = ap.parse_args()
    if a.cmd == "live":
        rows, ms = json.load(open(LIVE_LIST)), []
        for i, (fn, res, seen) in enumerate(rows):
            m = extract_live(LOGS / fn, seen, res)
            if m: ms.append(m)
            if i % 100 == 0: print(i, len(ms), flush=True)
        save("live", ms)
    elif a.cmd == "sim":
        files = []
        for p in a.paths:
            files += [str(p)] if p.endswith(".jsonl") else glob.glob(os.path.join(p, "**", "matches.jsonl"), recursive=True)
        ids, un, ms = sim_ids(), collections.Counter(), []
        for f in sorted(files):
            for l in open(f, encoding="utf8"):
                try: row = json.loads(l)
                except ValueError: continue
                if row.get("arm") != "plain": continue
                m = extract_sim(row, ids, un)
                if m: ms.append(m)
        print("unmapped SIM body names:", dict(un.most_common(15)))
        save("sim_" + a.name, ms)
    else:
        report(load("live"), [(n, load("sim_" + n)) for n in a.sim], a.out)


if __name__ == "__main__":
    main()
