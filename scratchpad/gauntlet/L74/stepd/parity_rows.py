"""Step d feature parity: the IMITATION row builder vs the RL / eval row builder on the SAME RoyaleSim states.

    ROYALE_RUNTIME=<runtime> python scratchpad/gauntlet/L74/stepd/parity_rows.py --replay <native replay_*.json> \
        [--crawl DIR] [--out parity.json]

Drives one replay with cue_drive's rules. At every recorded frame, while the SIM sits at that state, it builds the RL
side's view the way e1_eval.Match.prepare / gen_row do (noise off, no extrapolation): sim_compact (compact_raw + status
flags) -> from_engine -> body_only_board -> to_tokens; a PublicObserver per side fed the raw state (source 'sim', own
events from env.public_plays); e1_eval.sim_cue_rows on those tokens. Afterwards it builds the imitation rows from the
SAME recording with dataset_gen.replay_rows (+ cue_sidecar.replay_cue on the drive's cue bodies) and compares per row
(tick, side): unit tokens, opp_elixir (sc col 5 x 10 vs estimate_at), the detected opponent plays (which define
opp_cycle / opp_past), and the 22 cue floats. Prints PARITY_ROWS {...}.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import replace as dc_replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay", type=Path, required=True)
    ap.add_argument("--crawl", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    from pipeline.royale_runtime import activate
    stamp = activate()
    from pipeline import dataset_gen, engine_play
    from pipeline.e1_eval import sim_cue_rows
    from pipeline.obs_contract import from_engine, to_tokens
    from pipeline.public_observation import PublicObserver, body_only_board
    from scratchpad.gauntlet.L74.pro2.build_rows import card_catalog
    from scratchpad.gauntlet.L74.stepd import cue_drive as CD
    from scratchpad.gauntlet.L74.stepd.cue_sidecar import CUE_SCALE, replay_cue

    native = json.loads(a.replay.read_text(encoding="utf-8"))
    tag = str(native["tag"])
    if a.crawl:
        battles, plays = CD.load_crawl(a.crawl)
        source = CD.source_from_crawl(tag, battles[tag], plays.get(tag, [])) if tag in battles else CD.source_from_native(native)
    else:
        source = CD.source_from_native(native)
    decks: dict = {}                            # side -> (Deck, engine names), set at the first frame
    rl = {}                                     # (tick, side) -> dict(tok, est, cue) at the first frame of that tick
    obs = {s: None for s in (0, 1)}             # RL observers fed the SAME frames the recording keeps (builder parity)
    obs10 = {s: None for s in (0, 1)}           # ... fed only every 10th tick (the RL decide_every cadence)
    memo_il, memo_rl = {}, {}

    def on_frame(env, fr, kind):
        fr["cue"] = CD.cue_bodies(env, memo_il)                    # the imitation side's cue bodies (cue_drive)
        if kind != "frame":                                        # pre-act play frames: the recording's observers
            return                                                 # never read them (recording_observers)
        raw = env.raw()
        tick = int(raw["tick"])
        for s in (0, 1):
            if obs[s] is None:
                sched = getattr(env, "elixir_regen_schedule", None)
                obs[s], obs10[s] = PublicObserver(s, schedule=sched), PublicObserver(s, schedule=sched)
                names = [env.names[c] + ("@evolution" if f == 1 else "@hero" if f == 2 else "")
                         for c, f in zip(env.deck_ids[s], env.loaded_forms[s])]
                decks[s] = (dataset_gen.side_deck(names), names)
            own = [e for e in getattr(env, "public_plays", []) + getattr(env, "own_ability_events", []) if e["side"] == s]
            for o in (obs[s], obs10[s]) if tick % 10 == 0 else (obs[s],):
                o.own_events = own
                o.update(raw, source="sim")
            o = obs[s]
            if (tick, s) in rl:
                continue
            compact = engine_play.compact_raw(raw)                   # e1_eval.sim_compact (fv >= 3 keeps status flags)
            for e, orig in zip(compact["entities"], raw.get("entities", [])):
                e["status_flags"] = orig["status_flags"]
            bs = from_engine(compact, s, decks[s][0], engine_deck=decks[s][1], unmapped=set(), feature_version=5)
            view = body_only_board(dc_replace(bs, opp_elixir=o.estimate_at(tick)))
            tok, mask, sc = to_tokens(view, 64)
            stub = SimpleNamespace(env=env, _obs=(tok, mask), side=s)
            stub.__dict__["_cue_memo"] = memo_rl                     # sim_cue_rows keeps its memo on the match
            c = sim_cue_rows(stub)
            rl[tick, s] = dict(tok=tok[mask], est=float(o.estimate_at(tick)), est10=float(obs10[s].estimate_at(tick)),
                               cue=c[mask], sc5=float(sc[5]))

    catalog = card_catalog()
    import os
    hero = any(t == "ice-wizard-hero" for d in source["decks"].values() for t in d)
    os.environ["ROYALE_HEROIW_FORM"] = "hero" if hero else "normal"
    from scratchpad.gauntlet.L74.pro2.build_rows import drive
    record = frozenset(int(f["tick"]) for f in native.get("frames") or [])
    rec = drive(source, catalog, on_frame=on_frame, record_ticks=record)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"replay_{tag}.json"
        p.write_text(json.dumps(rec), encoding="utf-8")
        il = dataset_gen.replay_rows(str(p), wait_stride=40, play_window=20, shift_ticks=0, feature_version=5)
    if "error" in il:
        raise SystemExit(f"replay_rows failed: {il['error']}")
    # imitation cue rows from the drive's bodies (fid forced to 1: this check is about the builders, not fidelity)
    rows = [(int(f["tick"]), -1, f) for f in rec["frames"]] + [(int(f["tick"]), int(f["play_index"]), f) for f in rec["play_frames"]]
    rows.sort(key=lambda r: (r[0], r[1]))
    off, bodies = [0], []
    for _, _, f in rows:
        bodies.extend(f["cue"]); off.append(len(bodies))
    cz = dict(tick=np.asarray([r[0] for r in rows]), pidx=np.asarray([r[1] for r in rows]), fid=np.ones(len(rows), np.float32),
              off=np.asarray(off), bodies=np.asarray(bodies, np.float32).reshape(-1, CD.BODY_HEAD + 22))
    cue_il, status, _, tfid = replay_cue(il["tok"], il["n_tok"], il["tick"], il["side"], il["y_gate"], cz, 0.0, token_gate=False)

    starts = np.concatenate([[0], np.cumsum(il["n_tok"])])
    n = dict(rows=0, wait_rows=0, tok_equal=0, cue_equal=0, cue_rows_compared=0, est_abs_err=[], est10_abs_err=[],
             missing_rl=0)
    for i in range(len(il["tick"])):
        t, s, g = int(il["tick"][i]), int(il["side"][i]), int(il["y_gate"][i])
        r = rl.get((t, s))
        if r is None:
            n["missing_rl"] += 1
            continue
        n["rows"] += 1
        tok_il = il["tok"][starts[i]:starts[i + 1]]
        same_tok = tok_il.shape == r["tok"].shape and np.allclose(tok_il, r["tok"], atol=1e-6)
        n["est_abs_err"].append(abs(float(il["sc"][i, 5]) * 10.0 - r["est"]))
        n["est10_abs_err"].append(abs(float(il["sc"][i, 5]) * 10.0 - r["est10"]))
        if g:                                   # a play row reads the PRE-ACT play frame; the RL view at that tick is
            continue                            # the first frame of the tick (they differ after a same-tick play)
        n["wait_rows"] += 1
        n["tok_equal"] += same_tok
        if same_tok:
            n["cue_rows_compared"] += 1
            q = np.rint(np.clip(r["cue"], 0, 1) * CUE_SCALE).astype(np.uint8)
            n["cue_equal"] += bool(np.array_equal(cue_il[starts[i]:starts[i + 1]], q))
    def summ(e):
        e = np.asarray(e or [0.0])
        return dict(mean=round(float(e.mean()), 4), p95=round(float(np.quantile(e, .95)), 4), max=round(float(e.max()), 4),
                    share_le_0p05=round(float(np.mean(e <= 0.05)), 4))
    err, err10 = summ(n.pop("est_abs_err")), summ(n.pop("est10_abs_err"))
    il_obs = sorted((int(e["tick"]), int(e["side"]), str(e["card"])) for e in il.get("actual_plays") or [])
    rl_obs = sorted((int(e["tick"]), int(e["side"]), str(e["card"])) for o in obs.values() if o for e in o.plays)
    rl10 = sorted((int(e["tick"]), int(e["side"]), str(e["card"])) for o in obs10.values() if o for e in o.plays)
    res = dict(tag=tag, source=source["source"], runtime=stamp.get("runtime_id"), **n,
               opp_elixir_abs_err_same_frames=err, opp_elixir_abs_err_rl_cadence10=err10,
               opp_plays_il=len(il_obs), opp_plays_rl=len(rl_obs), opp_plays_equal=il_obs == rl_obs,
               opp_plays_symdiff=len(set(il_obs) ^ set(rl_obs)), opp_plays_rl10=len(rl10),
               opp_plays_symdiff_rl10_cards=len({(s, c) for _, s, c in il_obs} ^ {(s, c) for _, s, c in rl10}),
               cue_status=np.bincount(status, minlength=5).tolist(),
               token_fid_self=dict(mean=round(float(np.nanmean(tfid)), 4), share_ge_090=round(float(np.nanmean(tfid >= 0.9)), 4)))
    print("PARITY_ROWS", json.dumps(res))
    if a.out:
        a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
