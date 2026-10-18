"""B6 stage B offline check: recent live logs through the LIVE feature builder (L68/live_reader/ability_head_live.py) and a
checkpoint's learned ability head -- no device, read-only on the logs, CPU at below-normal priority.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/ability_live/replay_head.py [--logs GLOB] [--ckpt CK] [--max N]

At every LOGGED decision (live_play --public-audit: one every >= 10 ticks, the SIM's decide_every) where --iw-press head
would have decided -- the button read ready, no ability press pending at the frame's start, no card tap pending (a
logged decision implies it), my hero on the board:
  g        = the checkpoint's trunk on that decision's model batch, rebuilt by L73/lethal_rocket/rebuild.py (the existing
             live-log rebuild; its own_ability token with the log's --hero-ability-spec)
  features = ability_head_live.head_features on the same tick's 'frame' event (every reader frame, --log-frames);
             deploy = the hero's 'confirmed' / 'late_landing' tick, presses = 'ability_confirmed' since it
-> p and the greedy press (ability_head_live.head_press = e1_eval.ability_decide). Per hero deployment: the head's first
press vs the rule's logged press (seconds after the deploy). The live head would decide on EVERY ready frame (~5x the
logged cadence); after the rule pressed, that deployment has no ready frame left (counterfactual cut). Feature checks:
NaN, and the analytic bounds of each SIM feature's definition (no SIM training rows were saved to compare against).
"""
from __future__ import annotations

import argparse
import functools
import glob
import json
import math
import sys
from collections import Counter
from pathlib import Path

try:                                       # the laptop is shared with live play
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass

REPO = Path(__file__).resolve().parents[4]
for p in (REPO, REPO / "scratchpad/gauntlet/L68/live_reader", REPO / "scratchpad/gauntlet/L73/lethal_rocket"):
    sys.path.insert(0, str(p))
import torch  # noqa: E402

import ability_head_live as AL  # noqa: E402

CKPT = r"C:/Users/benpe/pod_backup_weekend/pod1016_gae_ab/cb_ab/icebow/data/bench/rl_royale/rlarm_gae_ab/rlarm_gae_ab_u0065_grafted.pt"
LOGS = str(REPO / "scratchpad/gauntlet/L68/live_reader/live_play_20261017_18*.jsonl")
NAMES = ["age_s/30", "hero_hp", "near_unit/10", "near_struct/10", "n3/5", "hp3/2000", "n5/5", "hp5/2000", "hero_far_half",
         "near_tower/10", "elixir/10", "minute/3", "phase/3", "crowns/3", "n_rad/5", "el_rad/10", "tower_rad", "presses"]


def bounds_ok(j, v):
    """The SIM feature's own definition range (royale_env._ability_head_features); pressable = elixir >= the cost 2."""
    if j in (2, 3, 9):
        return 0 <= v <= 4.0
    if j == 1:
        return 0 <= v <= 1
    if j in (8, 16):
        return v in (0.0, 1.0)
    if j == 10:
        return 0.2 - 1e-9 <= v <= 1.0
    if j == 11:
        return v in (0.0, 1 / 3, 2 / 3, 1.0)
    if j == 12:
        return v in (1 / 3, 2 / 3, 1.0)
    if j == 13:
        return -1 <= v <= 1
    if j == 17:
        return v == 0.0                    # max_charges 1: a pressable button was never pressed by this body
    return v >= 0


def replay(log, rb, ability, ckpt):
    m = rb.Match(log, ckpt)
    side = m.side
    heroes = [n for n, f in m.deck.values() if f == 2]
    if not heroes:
        return None
    card = heroes[0]
    hids = {next(c for c, n in AL._names().items() if n == card and 26000000 <= c < 27000000)}
    bstate, ab_pending, ab_start, frame = None, False, False, None
    deps, presses, last_ab = [], [], None
    rows, rule = [], []
    di, ready_frames = -1, 0
    for e in m.ev:
        ev = e.get("event")
        if ev == "frame":
            frame, ab_start = e, ab_pending
            ready_frames += bstate == "ready" and not ab_pending
        elif ev == "button":
            bstate = e["state"]
        elif ev == "ability":
            ab_pending, last_ab = True, e["tick"]
            rule.append(e)
        elif ev in ("ability_confirmed", "ability_unconfirmed"):
            ab_pending = False
            if ev == "ability_confirmed" and last_ab is not None:
                presses.append(last_ab)
        elif ev in ("confirmed", "late_landing") and e.get("name") == card:
            deps.append(int(e["tick"]))
        elif ev == "decision":
            di += 1
            tick = int(e["public"]["raw_tick"])
            if bstate != "ready" or ab_start or frame is None or int(frame["tick"]) != tick or tick < 150:
                continue
            ents = [dict(side=x[0], x=x[1], y=x[2], card_id=x[3], hp=x[4], max_hp=x[5], kind=x[6], address=x[7])
                    for x in frame["ents"]]
            from pipeline.reader_identity_aliases import dedupe_hero_bodies
            f = dedupe_hero_bodies({"game_tick": tick, "entities": ents})

            def deploy(c, t):                  # the log's version of ability_head_live.deploy_state
                dep = max([d for d in deps if d <= t], default=t)
                return dep, sum(1 for x in presses if dep <= x <= t)

            def g_of(i=di):
                with torch.no_grad():
                    return m.model(m.batch(i)[0])["g"]
            press, why, feat = AL.decide_board(f, side, hids, float(frame["elixir"]), deploy, g_of, ability)
            if feat is None:
                rows.append(dict(tick=tick, hero=False, why=why))
                continue
            rows.append(dict(tick=tick, hero=True, dep=deploy(card, tick)[0], p=float(why.split("=")[1]), press=press,
                             feat=feat))
    return dict(card=card, rows=rows, rule=rule, deps=deps, ready_frames=ready_frames, side=side,
                spec=m.start.get("hero_ability_spec"))


def report(name, r, out):
    rows = [x for x in r["rows"] if x["hero"]]
    skipped = Counter(x["why"] for x in r["rows"] if not x["hero"])
    head = [x for x in rows if x["press"]]
    deps = sorted(set(r["deps"]))
    first = {}                                  # deployment -> the head's first press (the only one live would make)
    for x in head:
        first.setdefault(max(d for d in deps if d <= x["tick"]), x)
    out(f"== {name} (side {r['side']}, {r['card']}, hero_ability_spec {r['spec']}): {r['ready_frames']} ready frames; "
        f"{len(rows)} head decisions at logged decisions (not decided: {dict(skipped)}); head presses {len(first)} "
        f"({len(head)} decisions with p > 0.5); rule presses {len(r['rule'])}")
    if rows:
        ps = sorted(x["p"] for x in rows)
        out(f"   p: min {ps[0]:.4f} median {ps[len(ps) // 2]:.4f} max {ps[-1]:.4f}")
    for k, d in enumerate(deps):
        end = deps[k + 1] if k + 1 < len(deps) else 10 ** 9
        win = [x for x in rows if d <= x["tick"] < end]
        rp = [e for e in r["rule"] if d <= e["tick"] < end]
        hp = [x for x in win if x["press"]]
        at = next((x for x in win if rp and x["tick"] == rp[0]["tick"]), None)   # the head on the rule's press frame
        ages = lambda t: f"{(t - d) / 20:.1f}s"  # noqa: E731
        out(f"   deploy t={d / 20:.1f}s: {len(win)} head decisions, max p {max((x['p'] for x in win), default=0):.3f}; "
            f"head first press {ages(hp[0]['tick']) + ' (p=%.3f)' % hp[0]['p'] if hp else 'none'}"
            f"{' (before the rule)' if hp and rp and hp[0]['tick'] < rp[0]['tick'] else ''}; "
            f"rule press {ages(rp[0]['tick']) if rp else 'none'}"
            f"{' [' + rp[0]['why'][:60] + ']' if rp else ''}"
            f"{'; head p on that frame %.3f' % at['p'] if at else ''}")
    bad = Counter()
    for x in rows:
        for j, v in enumerate(x["feat"]):
            if math.isnan(v) or not bounds_ok(j, v):
                bad[NAMES[j] if j < len(NAMES) else f"onehot{j - 18}"] += 1
        if sum(x["feat"][18:]) != 1:
            bad["onehot_sum"] += 1
    out(f"   NaN / out-of-range: {dict(bad) if bad else 'none'}")
    return rows, head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=LOGS)
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("replay_head.out"))
    a = ap.parse_args()
    torch.set_num_threads(2)
    import rebuild as rb
    from pipeline.own_ability import tokens
    from pipeline.rl_royale import load_ability_head
    ability = load_ability_head(a.ckpt)
    if ability is None:
        raise SystemExit(f"{a.ckpt} has no ability head")
    cache = {}
    load = rb.load_model

    def cached(path, device):
        if path not in cache:
            cache[path] = load(path, device)
        return cache[path]
    rb.load_model = cached
    lines = []

    def out(s):
        print(s, flush=True)
        lines.append(s)
    out(f"checkpoint {a.ckpt}\nlogs {a.logs} (first {a.max} with hero decisions)")
    allrows, n = [], 0
    for log in sorted(glob.glob(a.logs)):
        if n >= a.max:
            break
        try:
            head = json.loads(open(log, encoding="utf-8").readline())
            rb.ability_tokens = functools.partial(tokens, hero_spec=head.get("hero_ability_spec") or "off")
            r = replay(log, rb, ability, a.ckpt)
        except Exception as exc:                   # a log without public-audit decisions / frames
            out(f"skip {Path(log).name}: {exc!r}")
            continue
        if r is None or not r["rows"]:
            out(f"skip {Path(log).name}: no hero decision")
            continue
        rows, _ = report(Path(log).name, r, out)
        allrows += rows
        n += 1
    if allrows:
        out(f"== all {n} matches: {len(allrows)} head decisions, {sum(x['press'] for x in allrows)} with p > 0.5")
        for j, nm in enumerate(NAMES):
            v = sorted(x["feat"][j] for x in allrows)
            out(f"   {j:2d} {nm:14s} min {v[0]:8.4f}  median {v[len(v) // 2]:8.4f}  max {v[-1]:8.4f}")
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
