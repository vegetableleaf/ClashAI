"""S10: supervised advantage update on the fork-scored drill moments, anchored to the starting policy.

    python train_drills.py --ckpt CK --rows ROWS_DIR --matches RUN_DIR[,RUN_DIR] --verdicts V.json --out OUT.pt [--epochs 3 --max-min 60]

Drill rows (rows/fork_<drill>_<tag>_<tick>.npz, written by mech_fork at every fork): the model's input row, the allowed-slot mask and
the root decision of each arm.  Label = the root decision of the arm the fork verdict named better for that drill (verdicts.json:
{"D1": "do"|"alt"|"none"}); a drill with "none" is not trained.  Weight per moment = 1 where the winning arm won this moment's match,
0.5 on a tie, 0 where it lost (advantage-filtered).  Loss per drill row: BCE(gate logit - logit(0.35), play) + (if the label plays)
CE(card over allowed slots) + CE(cell head of the labelled card).
Anchor: ordinary rows (rows/ord_*.npz, ~1 in 25 learner decisions of the same matches): KL(start || current) of the gate Bernoulli and of the
card softmax over allowed slots, weighted --kl (large).  After each epoch the held-out ordinary rows give the share whose top allowed
card differs from the start policy; training stops, and the previous epoch is kept, once that share exceeds --max-drift (1%).
Public information only: the rows are the model's own inputs."""
import argparse, glob, json, math, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getcwd())
import numpy as np, torch, torch.nn.functional as F  # noqa: E402
from pipeline import e1_eval as E  # noqa: E402
from pipeline.model_gen import load_model  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ckpt", required=True); ap.add_argument("--rows", required=True); ap.add_argument("--matches", required=True)
ap.add_argument("--verdicts", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--epochs", type=int, default=3); ap.add_argument("--max-min", type=float, default=60.0)
ap.add_argument("--lr", type=float, default=1e-5); ap.add_argument("--kl", type=float, default=50.0)
ap.add_argument("--max-drift", type=float, default=0.01); ap.add_argument("--bs", type=int, default=64); ap.add_argument("--ord-bs", type=int, default=256)
ap.add_argument("--device", default="cuda"); ap.add_argument("--tau", type=float, default=0.35)
a = ap.parse_args()
t_start = time.time()
dev = torch.device(a.device if torch.cuda.is_available() else "cpu")
model, st = load_model(a.ckpt, dev)
model.eval()
pol = E.GenPolicy(model, st["card_vocab"])
keys = list(E.gen_row_keys(model))
V = json.load(open(a.verdicts))

# per-moment advantage of the winning arm (win score of that arm minus the other's; 'alt' of D10 = the model's own play)
SC = {"win": 1.0, "draw": 0.5, "loss": 0.0}
adv = {}
for d in a.matches.split(","):
    for ln in open(os.path.join(d, "matches.jsonl")):
        r = json.loads(ln)
        for o in (r.get("mech") or {}).get("opps", []):
            if o.get("arms") and o.get("drill") in V and V[o["drill"]] in ("do", "alt") and "Ares" in o:
                win_arm = V[o["drill"]]
                oth = "alt" if win_arm == "do" else "do"
                w, l = o["arms"].get(win_arm), (o["arms"].get(oth) or o["Ares"])
                if w is None:
                    continue
                adv[(o["drill"], r["tag"], o["t0"])] = SC[w["outcome"]] - SC[l["outcome"]]


def stack(rs):
    b = {k: torch.from_numpy(np.ascontiguousarray(np.stack([r[k] for r in rs]))).to(dev) for k in keys}
    b["allowed"] = torch.from_numpy(np.stack([r["allowed"] for r in rs])).to(dev)
    return b


drill, orows = [], []
for f in sorted(f for rd in a.rows.split(",") for f in glob.glob(os.path.join(rd, "*.npz"))):
    n = os.path.basename(f)[:-4]
    z = dict(np.load(f))
    if n.startswith("ord_"):
        orows.append(z)
    elif n.startswith("fork_"):
        dr = str(z["drill"])
        if V.get(dr) not in ("do", "alt"):
            continue
        arm = V[dr]
        if f"{arm}_play" not in z:
            continue
        tag = n[len(f"fork_{dr}_"):].rsplit("_", 1)[0]
        t0 = int(z["tick"])
        # tag was stored with ':' -> '_'; match by the sanitised tag
        w = next((v for (d_, tg, tt), v in adv.items() if d_ == dr and tt == t0 and tg.replace(":", "_") == tag), None)
        if w is None:
            continue
        wt = 1.0 if w > 0 else (0.5 if w == 0 else 0.0)
        if wt > 0:
            z["_w"], z["_play"], z["_slot"], z["_cell"] = wt, int(z[f"{arm}_play"]), int(z[f"{arm}_slot"]), int(z[f"{arm}_cell"])
            drill.append(z)
print(f"drill rows {len(drill)} (trained drills {[k for k, v in V.items() if v in ('do', 'alt')]}); ordinary rows {len(orows)}", flush=True)
if not drill or len(orows) < 100:
    print("NOTHING TO TRAIN (no drill with a verdict, or too few ordinary rows)")
    sys.exit(3)
rng = np.random.default_rng(0)
perm = rng.permutation(len(orows))
hold = [orows[i] for i in perm[:max(50, len(orows) // 5)]]
anchor = [orows[i] for i in perm[len(hold):]]


@torch.no_grad()
def start_out(rs):
    outs = []
    for i in range(0, len(rs), 256):
        b = stack(rs[i:i + 256])
        enc, h = pol.heads_t(b)
        outs.append((h["gate"].float(), h["card"].float()))
    return torch.cat([o[0] for o in outs]), torch.cat([o[1] for o in outs])


g0_a, c0_a = start_out(anchor)
g0_h, c0_h = start_out(hold)
allowed_h = torch.from_numpy(np.stack([r["allowed"] for r in hold])).to(dev)
top0 = c0_h.masked_fill(~allowed_h, -1e9).argmax(-1)
_t2 = c0_h.masked_fill(~allowed_h, -1e9).topk(2, -1).values
material = (_t2[:, 0] - _t2[:, 1]) >= 0.05      # rows whose start top-1 / top-2 logit margin is >= 0.05; a flip of a near-tie is not a behaviour change
play0 = (torch.sigmoid(g0_h) > a.tau)


def kl_terms(gate, card, g0, c0, allowed):
    p0, lp0 = torch.sigmoid(g0), None
    kg = p0 * (F.logsigmoid(g0) - F.logsigmoid(gate)) + (1 - p0) * (F.logsigmoid(-g0) - F.logsigmoid(-gate))
    c = card.masked_fill(~allowed, -1e9)
    q0 = torch.softmax(c0.masked_fill(~allowed, -1e9), -1)
    kc = (q0 * (torch.log_softmax(c0.masked_fill(~allowed, -1e9), -1) - torch.log_softmax(c, -1))).sum(-1)
    return kg.mean() + kc.mean()


@torch.no_grad()
def drift():
    gs, cs = [], []
    for i in range(0, len(hold), 256):
        b = stack(hold[i:i + 256])
        enc, h = pol.heads_t(b)
        gs.append(h["gate"].float()); cs.append(h["card"].float())
    g, c = torch.cat(gs), torch.cat(cs)
    top = c.masked_fill(~allowed_h, -1e9).argmax(-1)
    return float(((top != top0) & material).float().mean()), float(((torch.sigmoid(g) > a.tau) != play0).float().mean())


opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.0)
logit_tau = math.log(a.tau / (1 - a.tau))
best = {k: v.detach().clone() for k, v in model.state_dict().items()}
log = []
stopped = "epochs done"
nstep = 0
for ep in range(a.epochs):
    order = rng.permutation(len(drill))
    for i in range(0, len(order), a.bs):
        if (time.time() - t_start) / 60 > a.max_min:
            stopped = "time cap"
            break
        rs = [drill[j] for j in order[i:i + a.bs]]
        b = stack(rs)
        enc, h = pol.heads_t(b)
        w = torch.tensor([float(r["_w"]) for r in rs], device=dev)
        play = torch.tensor([float(r["_play"]) for r in rs], device=dev)
        loss = (w * F.binary_cross_entropy_with_logits(h["gate"].float() - logit_tau, play, reduction="none")).sum() / w.sum()
        pi = play.nonzero().squeeze(-1)
        if len(pi):
            slot = torch.tensor([int(r["_slot"]) for r in rs], device=dev)
            cell = torch.tensor([int(r["_cell"]) for r in rs], device=dev)
            lc = h["card"].float().masked_fill(~b["allowed"], -1e9)
            ce_card = F.cross_entropy(lc[pi], slot[pi], reduction="none")
            cl = pol.cell_logits({k: v[pi] for k, v in enc.items()}, slot[pi])
            ce_cell = F.cross_entropy(cl.float(), cell[pi], reduction="none")
            loss = loss + ((w[pi] * (ce_card + ce_cell)).sum() / w.sum())
        ai = rng.integers(0, len(anchor), a.ord_bs)
        ba = stack([anchor[j] for j in ai])
        _, ha = pol.heads_t(ba)
        kl = kl_terms(ha["gate"].float(), ha["card"].float(), g0_a[ai], c0_a[ai], ba["allowed"])
        tot = loss + a.kl * kl
        opt.zero_grad(set_to_none=True)
        tot.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        log.append((float(loss), float(kl)))
        nstep += 1
        if nstep % 2 == 0:                                   # drift guard every 5 steps: keep the last state within the budget
            dt, dp = drift()
            if dt > a.max_drift:
                model.load_state_dict(best)
                stopped = f"step {nstep}: top card moved {100 * dt:.2f}% > {100 * a.max_drift:.0f}%: kept the state at step {nstep - 2}"
                break
            best = {k: v.detach().clone() for k, v in model.state_dict().items()}
    if stopped.startswith("step"):
        break
    dt, dp = drift()
    print(f"epoch {ep + 1}: drill loss {np.mean([l[0] for l in log[-50:]]):.3f} kl {np.mean([l[1] for l in log[-50:]]):.4f} | "
          f"held-out ordinary rows: top-card change (start margin >= 0.05) {100 * dt:.2f}%  play/no-play change {100 * dp:.2f}%", flush=True)
    if dt > a.max_drift:
        model.load_state_dict(best)
        stopped = f"epoch {ep + 1} moved the top card {100 * dt:.2f}% > {100 * a.max_drift:.0f}%: kept epoch {ep}"
        break
    best = {k: v.detach().clone() for k, v in model.state_dict().items()}
    if stopped == "time cap":
        break
torch.save({**st, "model": {k: v.cpu() for k, v in model.state_dict().items()}, "drill_trained": {"verdicts": V, "stopped": stopped,
            "rows": len(drill), "ordinary": len(orows)}}, a.out)
dt, dp = drift()
print(f"SAVED {a.out}; stopped: {stopped}; final held-out top-card change {100 * dt:.2f}%, play change {100 * dp:.2f}%")
json.dump({"stopped": stopped, "drill_rows": len(drill), "ordinary_rows": len(orows), "top_card_change_pct": 100 * dt,
           "play_change_pct": 100 * dp}, open(a.out + ".json", "w"))
