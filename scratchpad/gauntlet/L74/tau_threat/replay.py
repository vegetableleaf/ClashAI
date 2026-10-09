"""Replay of --tau-threatened X on the live decision states 10-05..10-08 23:12 (the L74 mistake catalogue's live.pkl.gz:
533 matches with decision logs). Single process, below-normal priority (mistakes.py sets it).

  PYTHONPATH=. icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/tau_threat/replay.py

M4 run = the catalogue's own definition (copied loop): tower lost HP within +-1 s, an enemy body within 8 tiles of it, a
non-X-Bow/Rocket card affordable, no play pending, model did not play; consecutive states of the same tower <= 30 ticks apart
merge; run >= 2 s.  STRICT = >= 2 s holding a 3+ elixir card.  Causal 'threatened' (what the option can see): at state j,
some tower k lost HP at a state with t_j - t_loss <= 40 ticks (2 s) AND an enemy body within 8 tiles of tower k at j.
For X the first state of a run that is threatened with p_play > X is the play (card = the logged top affordable card).
"""
import sys, os, math, collections, json, gzip
sys.path.insert(0, "C:/Users/benpe/ClashBot/.claude/worktrees/agent-a062325a516da5d40/scratchpad/gauntlet/L74/mistakes")
sys.path.insert(0, "C:/Users/benpe/ClashBot/.claude/worktrees/agent-a71df5859a8006344")
import numpy as np
import mistakes as K
from pipeline.decision_options import gate_rate

XS = (0.10, 0.15, 0.20, 0.25)
TW = K.TW
AIRKILL = {"balloon", "balloon_hero", "lava_hound"}           # building-targeting air
GROUND_ONLY = {"Knight", "Skeletons", "Log", "Xbow"}          # cannot hit air (Tornado: no damage worth the name)
AA = {"Knight", "Skeletons", "Xbow"}                          # air_answer block's is_ground_only (troops/buildings; Log is a spell, not covered)
OUT = "C:/Users/benpe/ClashBot/.claude/worktrees/agent-a71df5859a8006344/scratchpad/gauntlet/L74/tau_threat/"


def loss_times(M):
    """per tower: list of tick at which its HP first read lower than at the previous state."""
    out = {k: [] for k in ("mL", "mR", "mK")}
    for k in out:
        v = M.H[k]
        for i in range(1, len(v)):
            if v[i] is not None and v[i - 1] is not None and v[i] < v[i - 1]:
                out[k].append(M.T[i])
    return out


def threatened_state(M, j, losses):
    t, x = M.T[j], M.S[j]
    for k, ts in losses.items():
        if any(0 <= t - tl <= 40 for tl in ts):
            if any(math.hypot(b[1] - TW[k][0], b[2] - TW[k][1]) <= 8.0 for b in x[3]):
                return k
    return None


def runs_of(M):
    S = M.S
    runs, cur = [], None
    for j, x in enumerate(S):
        t = x[0]; el = x[1] or 0.0; hand = x[2] or ()
        hurt = None
        for k in ("mL", "mR", "mK"):
            if M.dmg(k, t - 20, t + 20) > 0:
                if any(math.hypot(b[1] - TW[k][0], b[2] - TW[k][1]) <= 8.0 for b in x[3]):
                    hurt = k; break
        aff = [c for c in hand if c not in ("Xbow", "Rocket") and K.COST.get(c, 9) <= el]
        d = x[5]
        idle = hurt and aff and d is not None and not d[0] and not M.pending(t)
        if idle:
            if cur and t - cur["t1"] <= 30 and cur["k"] == hurt:
                cur["t1"] = t; cur["states"].append(j)
            else:
                cur = dict(k=hurt, t0=t, t1=t, states=[j]); runs.append(cur)
        elif cur and t - cur["t1"] > 30:
            cur = None
    for r in runs:
        r["dur"] = (r["t1"] - r["t0"]) / 20.0 + 0.5
        ns = sum(1 for j in r["states"] if any(c not in ("Xbow", "Rocket") and 3 <= K.COST.get(c, 9) <= (S[j][1] or 0)
                                               for c in (S[j][2] or ())))
        r["strong_s"] = r["dur"] * ns / len(r["states"])
        r["dmg"] = M.dmg(r["k"], r["t0"], r["t1"] + 20)
        r["fell"] = M.fell(r["k"], r["t0"], r["t1"] + 100)
    return runs


def main():
    ms = [m for m in K.load_live() if m.get("res") in ("WIN", "LOSS", "DRAW") and os.path.basename(m["file"])[10:18] >= "20261005"]
    mins = sum(m["end"] for m in ms) / 20.0 / 60.0
    print("matches", len(ms), "minutes", round(mins))
    rows = []                                    # one row per M4 run (dur >= 2)
    thr_states = idle_thr = total_states = 0
    extra = collections.defaultdict(list)        # X -> per-match count of NON-run extra plays (threatened idle, p > X, not in a run)
    for m in ms:
        M = K.Match(m); S = M.S
        losses = loss_times(M)
        runs = [r for r in runs_of(M) if r["dur"] >= 2.0]
        in_run = {j for r in runs for j in r["states"]}
        flag = [threatened_state(M, j, losses) for j in range(len(S))]
        total_states += len(S); thr_states += sum(f is not None for f in flag)
        for r in runs:
            row = dict(file=m["file"], fam=m["fam"], res=m["res"], k=r["k"], t0=r["t0"], dur=r["dur"], dmg=r["dmg"], fell=r["fell"],
                       strict=r["strong_s"] >= 2.0, plays={})
            # deployed hazard (--gate-hazard-threatened 2, threat = tower lost HP within 2 s, no enemy condition):
            # survival of 'no play' over the run's waiting intervals
            surv = 1.0; prev_t = None
            for j in r["states"]:
                t = S[j][0]
                if prev_t is not None:
                    hz = any(0 <= t - tl <= 40 for ts in losses.values() for tl in ts)
                    if hz:
                        surv *= math.exp(-float(gate_rate(S[j][5][1])) * min(2.0, 0.05 * (t - prev_t)))
                prev_t = t
            row["hz_play_prob"] = 1.0 - surv
            for X in XS:
                hit = next((j for j in r["states"] if flag[j] and S[j][5][1] > X), None)
                if hit is not None:
                    x = S[hit]
                    near_air = sorted({b[0] for b in x[3] if b[0] in AIRKILL and math.hypot(b[1] - TW[r["k"]][0], b[2] - TW[r["k"]][1]) <= 12.0})
                    any_air = sorted({b[0] for b in x[3] if b[0] in AIRKILL})
                    row["plays"][X] = dict(lag=(x[0] - r["t0"]) / 20.0, card=x[5][2], p=x[5][1], tau=x[5][3], el=x[1], el_hand=list(x[2] or ()),
                                           near_air=near_air, any_air=any_air)
            rows.append(row)
        # extra threatened-idle plays outside the M4 runs (collateral): states that are threatened, no-play, affordable, p > X
        for X in XS:
            n = 0; last = -10 ** 9
            for j, x in enumerate(S):
                if j in in_run or flag[j] is None or x[5] is None or x[5][0] or x[5][4] or x[5][1] <= X: continue
                if M.pending(x[0]) or x[0] - last < 60: continue     # at most one counted play per 3 s (pending/lockout)
                n += 1; last = x[0]
            extra[X].append(n)
    json.dump(dict(rows=rows, mins=mins, n=len(ms), thr_frac=thr_states / total_states, extra={str(k): sum(v) for k, v in extra.items()}),
              open(OUT + "replay_rows.json", "w"), default=str)
    report(rows, mins, len(ms), thr_states / total_states, extra)


def report(rows, mins, n, thr_frac, extra):
    out = []
    P = out.append
    for name, rs in (("STRICT (>= 2 s with a 3+ elixir card)", [r for r in rows if r["strict"]]), ("ALL runs >= 2 s", rows)):
        P(f"=== {name}: {len(rs)} runs in {n} matches ({mins:.0f} min) = {len(rs) / mins * 10:.2f} per 10 min; fell {np.mean([r['fell'] for r in rs]):.1%}; "
          f"median dur {np.median([r['dur'] for r in rs]):.1f} s, mean {np.mean([r['dur'] for r in rs]):.1f} s, HP lost {np.mean([r['dmg'] for r in rs]):.0f} per run")
        hz = np.mean([r["hz_play_prob"] for r in rs])
        P(f"deployed hazard (--gate-hazard-threatened 2, expectation over the same waits): P(>= 1 play inside the run) = {hz:.1%}")
        for X in XS:
            got = [r for r in rs if X in r["plays"]]
            lag = [r["plays"][X]["lag"] for r in got]
            saved = [r["dur"] - r["plays"][X]["lag"] for r in got]
            P(f"  X={X:.2f}: {len(got)}/{len(rs)} = {len(got) / len(rs):.1%} runs get a play; lag from run start: median {np.median(lag):.1f} s, "
              f"p25 {np.percentile(lag, 25):.1f}, p75 {np.percentile(lag, 75):.1f}; seconds idle removed: {sum(saved) / mins * 10:.1f} per 10 min "
              f"of {sum(r['dur'] for r in rs) / mins * 10:.1f}")
            cards = collections.Counter(r["plays"][X]["card"] for r in got)
            go = sum(c for k, c in cards.items() if k in GROUND_ONLY)
            near = [r for r in got if r["plays"][X]["near_air"]]
            nearg = [r for r in near if r["plays"][X]["card"] in GROUND_ONLY]
            anyair = [r for r in got if r["plays"][X]["any_air"]]
            anyg = [r for r in anyair if r["plays"][X]["card"] in GROUND_ONLY]
            aa = [r for r in near if r["plays"][X]["card"] in AA]
            aa_all = [r for r in got if r["plays"][X]["card"] in AA]
            aa_alt = [r for r in aa if any(c not in AA and c not in ("Rocket",) and K.COST.get(c, 9) <= r["plays"][X]["el"] for c in r["plays"][X]["el_hand"])]
            P(f"        card: {dict(cards.most_common())}; ground-only {go / len(got):.1%}; balloon/lava hound within 12 tiles of the tower in "
              f"{len(near)}/{len(got)} plays, of which the card is ground-only in {len(nearg)} ({len(nearg) / max(len(got), 1):.1%} of all plays); "
              f"anywhere on the board: {len(anyair)} / {len(anyg)}; air_answer-covered (Knight/Skeletons/X-Bow) near an air unit: {len(aa)} "
              f"(an affordable non-covered card exists in hand in {len(aa_alt)}; the other {len(aa) - len(aa_alt)} would stay a WAIT); "
              f"covered cards in all plays {len(aa_all)}")
            el = [r["plays"][X]["el"] for r in got]
            P(f"        elixir at the play: median {np.median(el):.1f} (3.0-4.9: {np.mean([e < 5 for e in el]):.0%}); p_play at the play median "
              f"{np.median([r['plays'][X]['p'] for r in got]):.3f}")
        P("")
    P(f"threatened states (causal) = {thr_frac:.1%} of all decision states.  Plays X would add OUTSIDE the M4 runs (threatened, "
      f"waiting, affordable, p > X, <= 1 per 3 s): " + ", ".join(f"X={k:.2f}: {sum(v)} = {sum(v) / mins * 10:.2f}/10 min" for k, v in extra.items()))
    txt = "\n".join(out)
    print(txt)
    open(OUT + "replay_report.txt", "w").write(txt + "\n")


if __name__ == "__main__":
    main()
