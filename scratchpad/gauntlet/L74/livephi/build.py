"""Public decision audit -> the policy's to_tokens/PublicObserver encoding.

One CPU thread, resumable per-match shards, no network or live-script changes.
Full baseline inputs use reconstructed public history; next card is unlogged
and padded. Exact logged model-time board/object fields override reconstruction.
The fitted MLP uses ONLY the exactly reconstructable board feature projection.
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys
import time
import ctypes

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "phase_stats"))
import phase_stats as PS
from pipeline.obs_contract import BoardState, Unit, Tower, to_tokens, to_unit_forms
from pipeline.public_observation import PublicObserver
from pipeline.dataset_gen import SC_SLOT_COLS, card_key
from pipeline.model_gen import load_model
from pipeline.live_phi import features
from pipeline.train_s1 import MAX_U
from pipeline.live_gen import PAST_K
from pipeline.reader_identity_aliases import dedupe_hero_bodies

CKPT = ROOT / "icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt"
torch.set_num_threads(1)
if os.name == "nt":
    from ctypes import wintypes
    kernel=ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.SetPriorityClass.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.GetPriorityClass.argtypes=[wintypes.HANDLE]
    handle=kernel.GetCurrentProcess()
    if not kernel.SetPriorityClass(handle,0x4000) or kernel.GetPriorityClass(handle)!=0x4000:
        raise RuntimeError("cannot apply below-normal CPU job priority")
try:
    import psutil
    if os.name == "nt": psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except ImportError:
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""): h.update(buf)
    return h.hexdigest()


def outcome(data):
    tw = PS.towers(data["decisions"][-1])
    took = 3 - sum(v > 0 for k, v in tw.items() if k.startswith("enemy_"))
    lost = 3 - sum(v > 0 for k, v in tw.items() if k.startswith("own_"))
    return 1 if took > lost else 0 if took < lost else None


def tensor_batch(rows):
    return {k: torch.from_numpy(np.stack([r[k] for r in rows])) for k in rows[0]}


@torch.no_grad()
def baseline(model, b):
    # encode_gen's remaining spatial refinements do not modify g (the value input).
    tok = torch.cat([b["tok"], b["unit_form"].to(b["tok"].dtype).unsqueeze(-1)], -1)
    enc = model.encode(tok, b["mask"], model.global_features(b), b["past"].new_zeros(len(tok), 0, 4))
    p = model.value_head(enc["g"]).softmax(-1)
    value = p[:, 4:].sum(1) - p[:, :3].sum(1)
    gate = model.gate_head(enc["g"]).squeeze(-1).sigmoid()
    return value.numpy(), gate.numpy()


def tower_crown(sc):
    hp, known, alive = sc[:, 52:58], sc[:, 58:64], sc[:, 64:70] > .5
    frac = np.where(alive, np.where(known > .5, hp, 1), 0)
    own = np.where(~alive[:, 3], 3, (~alive[:, 4]).astype(int) + (~alive[:, 5]))
    foe = np.where(~alive[:, 0], 3, (~alive[:, 1]).astype(int) + (~alive[:, 2]))
    return .1 * (frac[:, :3].sum(1) - frac[:, 3:].sum(1) + own - foe)


def public_events(path):
    # Private/evaluation-only fields are discarded, including in frame events.
    with path.open("rb") as stream:
        for raw in stream:
            if not any(b'"event": "'+k+b'"' in raw[:80] for k in
                       (b"decision", b"frame", b"confirmed", b"ability_confirmed")): continue
            j = json.loads(raw)
            if j["event"] == "decision":
                p = j.get("public")
                if not p: continue
                keys = ("observer_side", "raw_tick", "model_tick", "own_elixir_raw", "model_own_elixir",
                        "opponent_elixir_estimate", "own_hand", "raw_bodies", "raw_projectiles",
                        "model_projectiles", "model_effects", "model_bodies", "model_towers", "feature_version")
                d = j.get("decision", {})
                yield {"event": "decision", "tick": j["tick"], "public": {k:p[k] for k in keys},
                       "decision": {k:d.get(k) for k in ("play", "name", "card", "form", "xy", "p_play")}}
            elif j["event"] == "frame":
                # The frame log also has an EVAL_ONLY opposing elixir field. Never
                # consult it: retain only public entities, clock and our own side.
                yield {"event":"frame", "tick":j["tick"], "side":j["my_side"],
                       "entities":[dict(zip(("side","x","y","card_id","hp","max_hp","kind","address"),x))
                                   for x in j["ents"]]}
            else:
                yield {k:j.get(k) for k in ("event", "tick", "name")}

def rebuild(events, gid):
    ds = [e for e in events if e["event"] == "decision"]
    deck = {}
    for d in ds:
        for h in d["public"]["own_hand"]:
            if h["deck_index"] >= 0 and h["name"]:
                deck[h["deck_index"]] = (gid[card_key(h["name"])], h["form"])
    if len(deck) != 8: raise ValueError("incomplete own deck")
    deck = sorted(deck.values())  # fixed own deck; no opponent deck is consulted
    pub = PublicObserver(ds[0]["public"]["observer_side"])
    past, pending, result, meta = [], [], [], []
    for e in events:
        if e["event"] == "frame":
            if e["side"] != pub.side: raise ValueError("frame observer side changed")
            frame=dict(game_tick=e["tick"],entities=e["entities"],projectiles=[],effects=[],players=[])
            pub.update(dedupe_hero_bodies(frame),source="reader")
            continue
        if e["event"] == "confirmed":
            cand = [q for q in pending if q["name"] == e["name"] and 0 <= e["tick"]-q["tick"] <= 100]
            if cand:
                q = cand[-1]; pending.remove(q)
                if q["xy"] is not None:
                    past.append([q["card"], q["form"], *q["xy"], e["tick"]*.05])
                    pub.own_events.append(dict(card=card_key(q["name"]), tick=e["tick"], side=pub.side, accepted=True, ability=False))
            continue
        if e["event"] == "ability_confirmed":
            pub.own_events.append(dict(card="ice-wizard", tick=e["tick"], side=pub.side, accepted=True, ability=True))
            continue
        p, d = e["public"], e["decision"]
        side, tick = p["observer_side"], p["model_tick"]
        # Only our player block; PublicObserver normalizes public bodies/projectiles.
        frame = dict(game_tick=e["tick"], entities=p["raw_bodies"], projectiles=p["raw_projectiles"], effects=[],
                     players=[dict(side=side, hand_deck_indices=[h["deck_index"] for h in p["own_hand"]],
                                   elixir_raw=p["own_elixir_raw"]*1e4)])
        # This is the same preprocessing performed by GenPilot.observe.
        pub.update(dedupe_hero_bodies(frame), source="reader")
        t = tick*.05
        bs = BoardState("live_mem", t, "tick", t>=120, t>=180, p["model_own_elixir"], True,
                        p["opponent_elixir_estimate"], (-1,)*4, -1,
                        tuple(Tower(**x) for x in p["model_towers"]),
                        tuple(Unit(**x) for x in p["model_bodies"]), ())
        tok, mask, sc = to_tokens(bs, MAX_U); sc[SC_SLOT_COLS] = 0
        ph = np.tile(np.array([0, 3, -1, -1, -1], np.float32), (PAST_K, 1))
        for i, q in enumerate(reversed(past[-PAST_K:])): ph[i] = [*q[:4], t-q[4]]
        hand = [(gid[card_key(h["name"])], h["form"]) if h["name"] else (0, 3) for h in p["own_hand"]]
        b = dict(tok=tok, mask=mask, sc=sc, unit_form=to_unit_forms(bs, MAX_U).astype(np.int64), past=ph,
                 hand_card=np.array([x[0] for x in hand], np.int64), hand_form=np.array([x[1] for x in hand], np.int64),
                 next_card=np.array(0, np.int64), next_form=np.array(3, np.int64),
                 deck_card=np.array([x[0] for x in deck], np.int64), deck_form=np.array([x[1] for x in deck], np.int64))
        b.update(pub.features(tick, gid))
        for key in ("projectiles", "effects"):
            b[key] = np.zeros_like(b[key])
            logged = np.asarray(p["model_"+key], np.float32)
            if len(logged): b[key][:len(logged)] = logged
        if 0 <= e["tick"] < 6000:
            result.append(b)
            meta.append([e["tick"], bool(d["play"]), next((h["cost"] for h in p["own_hand"] if h["name"]==d["name"]), 0),
                         float(d["p_play"] or 0), p["feature_version"]])
        if d["play"]: pending.append(dict(d, tick=e["tick"]))
    return result, np.array(meta)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=0); ap.add_argument("--seconds",type=float,default=240)
    ap.add_argument("--baseline",action="store_true",help="optional inline inference on later dates; default: baselines.py handles it after splitting")
    a=ap.parse_args(); t0=time.monotonic()
    shards=HERE/"shards"; shards.mkdir(exist_ok=True)
    manifest=HERE/"source_manifest.json"
    if not manifest.exists():
        paths=sorted(p for p in PS.LIVE.glob("live_play_*.jsonl") if p.name[10:18]>="20261008")
        manifest.write_text(json.dumps({"since":"20261008", "files":[p.name for p in paths]},indent=2))
    names=json.loads(manifest.read_text())["files"]
    model,ck=load_model(CKPT,torch.device("cpu")); model.eval().requires_grad_(False)
    gid={k:i for i,k in enumerate(ck["card_vocab"])}
    made=0
    for name in names:
        dst=shards/(name+".npz"); receipt=shards/(name+".json")
        if receipt.exists(): continue
        path=PS.LIVE/name
        data, reason=PS.read_live(path)
        y=outcome(data) if data else None
        r=dict(file=name, excluded=reason, label=y)
        if data: r.update(sha256=data["sha256"], bytes=data["bytes"], checkpoint=data["head"].get("ckpt"))
        if data and y is None: r["excluded"]="draw"
        if data and y is not None:
            rows, meta=rebuild(list(public_events(path)),gid)
            if not rows: raise ValueError(f"no gameplay rows {name}")
            xs, vs, gates=[],[],[]
            for i in range(0,len(rows),64):
                b=tensor_batch(rows[i:i+64])
                # Training uses no baseline outputs; reserve costly policy inference
                # for later-date calibration/test rows. NaNs cannot silently score.
                if a.baseline and name[10:18] >= "20261011":
                    v,g=baseline(model,b)
                else:
                    v=g=np.full(len(b["sc"]), np.nan, np.float32)
                xs.append(features(b).numpy()); vs.append(v); gates.append(g)
            allb=tensor_batch(rows)
            sample=np.linspace(0,len(rows)-1,min(4,len(rows))).astype(int)
            np.savez_compressed(dst, x=np.concatenate(xs), value=np.concatenate(vs), tc=tower_crown(allb["sc"].numpy()),
                                meta=meta, gate=np.concatenate(gates), **{"pd_"+k:v[sample].numpy() for k,v in allb.items()},
                                **({"batch_"+k:v.numpy() for k,v in allb.items()} if name[10:18]>="20261010" else {}))
            r.update(rows=len(rows), phase_counts=dict(collections.Counter(PS.phase(int(t)) for t in meta[:,0])),
                     feature_versions=sorted(set(meta[:,4].astype(int).tolist())), input_sha_verified=digest(path)==data["sha256"])
            if not r["input_sha_verified"]: raise RuntimeError("source changed during extraction")
        receipt.write_text(json.dumps(r,indent=2)); made+=1
        if made%10==0: print(f"processed={made} completed={sum(1 for _ in shards.glob('*.json'))}/{len(names)} seconds={time.monotonic()-t0:.1f}",flush=True)
        if (a.limit and made>=a.limit) or time.monotonic()-t0>a.seconds: break
    print("BUILD CHUNK END",made,round(time.monotonic()-t0,2),flush=True)


if __name__=="__main__": main()
