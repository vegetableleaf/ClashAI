"""THE PRIVILEGED-TEACHER GAP -- the go/no-go for distillation, measured before the long run.

HANDOFF section 6-PRIORITY-B. A MEASUREMENT tool; nothing in `icebow/src` or `hogeq/src` imports it.

THE QUESTION. The teacher sees ENGINE GROUND TRUTH: it forks `SimEngine` and reads exact positions,
exact hitpoints, the opponent's real hand. The student sees the DEGRADED observation the policy is
trained on (detector recall/precision, canvas presence, the lot). If the teacher's choices depend on
information the student cannot see, no amount of distillation reproduces them and the whole plan
caps out early. That is cheap to find out now and expensive to find out after a 20k-episode run.

Encouraging but NOT sufficient (`ledger/rollout_search.md`): handing the policy PERFECT perception
bought it +0.00 sigma on winrate, so its limitation is not information ACCESS. That is a fact about
the current policy's ability to USE clean input, not proof that these targets are LEARNABLE.

WHAT IS MEASURED. Held-out TOP-1 AGREEMENT with the teacher, on matches the student never trained
on, against two floors that make the number mean something:

  * THE BASE FLOOR -- the frozen policy's own agreement with the teacher on the same held-out rows.
    This is the number to beat. The corpus already carries the policy's greedy action per row, so
    the floor costs nothing and cannot drift from the student's evaluation.
  * THE MAJORITY-CLASS FLOOR -- what "always WAIT" scores. The teacher plays on roughly a fifth of
    decisions, so a gate accuracy near 0.78 is not a result, it is the class prior. Reported beside
    every gate number because without it the headline is unreadable.

SPLIT BY MATCH, NEVER BY DECISION. Consecutive decisions inside one match are ~0.6 s apart and
share nearly the same board; a random row split leaks the answer across it and would report a
flattering number that means nothing. The split here is on `match`.

TWO ARMS, because they answer different questions:
  * `heads`  -- trunk FROZEN, only the gate and card heads train. Asks: is the teacher's signal
                already linearly available in the representation the policy has? This is the arm
                closest to what the long run would actually do cheaply.
  * `full`   -- everything trains. Asks: is the signal learnable from the degraded observation AT
                ALL? A `full` that also fails is the clean negative worth having.

TARGETS: THE GATE AND THE CARD HEADS ONLY. Card+gate search is +22.0pp; adding cell search adds
+3.3pp, and placement is separately measured as worth ~nothing (the perfect-aim arm is +0.07
sigma). The corpus carries the teacher's cell for provenance and this script ignores it.

⚠ Run with the deck's own venv (`icebow\\.venv\\Scripts\\python.exe`) and `PYTHONHASHSEED=0`
exported in the ENVIRONMENT -- same two traps as the labeller.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(r"C:\Users\benpe\ClashBot")
sys.path.insert(0, str(ROOT / "scratchpad"))

import numpy as np                                                        # noqa: E402
import torch                                                              # noqa: E402
import torch.nn as nn                                                     # noqa: E402
import torch.nn.functional as F                                           # noqa: E402

import rollout_search as RS                                               # noqa: E402
from clashrl.model import PolicyNet                                       # noqa: E402

_NEG = -1e9


def load_corpus(path):
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    return z, meta


def build_net(meta, ckpt, device):
    """The student STARTS as the frozen policy, so 'agreement' measures what distillation ADDED
    rather than what a randomly-initialised head happens to score."""
    net = RS.PPONet(int(meta["obs_shape"][2]), int(meta["n_cards"]),
                    int(meta["n_cells"]), int(meta["threat_dim"])).to(device)
    ck = torch.load(ckpt, map_location="cpu")
    dropped = PolicyNet.load_compat(net.policy, ck["model"])
    if dropped:
        raise SystemExit(f"checkpoint tensors did not carry over: {dropped[:8]}")
    net.gate.load_state_dict(ck["gate"])
    if "value" in ck:
        net.value.load_state_dict(ck["value"])
    return net


def playable_mask(hand, elx, costs):
    """Exactly `Searcher._forward`'s rule: in hand AND affordable. Rebuilt rather than stored so a
    corpus can never disagree with the live masking."""
    return (hand > 0.5) & (costs[None, :] <= elx * 10.0 + 1e-6)


def forward_batch(net, z, idx, device, costs):
    obs = torch.from_numpy(z["obs"][idx]).float().permute(0, 3, 1, 2).to(device) / 255.0
    hand = torch.from_numpy(z["hand"][idx]).to(device)
    nxt = torch.from_numpy(z["nxt"][idx]).to(device)
    elx = torch.from_numpy(z["elx"][idx]).to(device)
    thr = torch.from_numpy(z["thr"][idx]).to(device)
    cq, _ceq, gq, _v, _vd = net(obs, hand, nxt, elx, thr)
    pm = playable_mask(hand, elx.squeeze(-1), costs)
    return cq, gq, pm


def decide(cq, gq, pm, tau):
    """`greedy_action`'s rule, batched: gate on sigmoid(g1-g0) > tau AND something playable, then
    argmax over the playable cards."""
    any_play = pm.any(dim=1)
    p_play = torch.sigmoid(gq[:, 1] - gq[:, 0])
    gate = (any_play & (p_play > tau)).long()
    card = cq.masked_fill(~pm, _NEG).argmax(dim=1)
    return gate, card


def agreement(gate, card, t_gate, t_card):
    """THREE numbers, because one hides the interesting failure.

    gate  -- did the student agree about playing at all
    card  -- given the TEACHER plays, did the student pick the same card (the head under test)
    joint -- the headline: same gate, and the same card whenever the teacher played
    """
    g_ok = (gate == t_gate)
    play = t_gate == 1
    c_ok = (card == t_card) & play
    joint = g_ok & (~play | (card == t_card))
    return {
        "gate": float(g_ok.float().mean()),
        "card_given_teacher_plays": float(c_ok[play].float().mean()) if int(play.sum()) else float("nan"),
        "joint": float(joint.float().mean()),
        "n": int(gate.numel()), "n_teacher_plays": int(play.sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "scratchpad" / "distill_corpus.npz"))
    ap.add_argument("--ckpt", default=str(ROOT / "scratchpad" / "_rs_policy.pt"))
    ap.add_argument("--holdout", type=float, default=0.30, help="fraction of MATCHES held out")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--arms", default="heads,full")
    ap.add_argument("--out", default=str(ROOT / "scratchpad" / "distill_student.json"))
    args = ap.parse_args()

    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("REFUSING: export PYTHONHASHSEED=0 in the ENVIRONMENT first "
                         "(see the labeller's docstring -- setdefault after start is a no-op).")

    torch.set_num_threads(1)
    device = torch.device("cpu")
    z, meta = load_corpus(args.corpus)
    costs = torch.tensor(meta["card_elixir"], dtype=torch.float32, device=device)
    tau = float(meta["gate_tau"])

    match = z["match"]
    t_gate_all = torch.from_numpy(z["teach_gate"].astype(np.int64))
    t_card_all = torch.from_numpy(z["teach_card"].astype(np.int64))
    p_gate_all = torch.from_numpy(z["pol_gate"].astype(np.int64))
    p_card_all = torch.from_numpy(z["pol_card"].astype(np.int64))

    # SPLIT ON MATCHES. Deterministic: the LAST `holdout` fraction of match ids, so re-running
    # this script on the same corpus always evaluates on the same states.
    ms = np.unique(match)
    n_hold = max(1, int(round(len(ms) * args.holdout)))
    hold_ms = set(ms[-n_hold:].tolist())
    te = np.where(np.isin(match, list(hold_ms)))[0]
    tr = np.where(~np.isin(match, list(hold_ms)))[0]
    if len(tr) == 0 or len(te) == 0:
        raise SystemExit(f"empty split: train={len(tr)} test={len(te)} from {len(ms)} matches")

    out = {
        "corpus_meta": meta,
        "split": {"train_rows": int(len(tr)), "test_rows": int(len(te)),
                  "train_matches": int(len(ms) - n_hold), "test_matches": int(n_hold),
                  "holdout_match_ids": sorted(int(m) for m in hold_ms)},
        "interpreter": sys.executable, "torch": torch.__version__,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
    }

    # ---- THE FLOORS -------------------------------------------------------
    out["floor_base_policy"] = agreement(p_gate_all[te], p_card_all[te], t_gate_all[te], t_card_all[te])
    tg = t_gate_all[te]
    maj = int(tg.float().mean() > 0.5)
    out["floor_majority_class"] = {
        "always": "PLAY" if maj else "WAIT",
        "gate": float((tg == maj).float().mean()),
        "teacher_play_rate_heldout": float(tg.float().mean()),
    }
    out["teacher_play_rate_train"] = float(t_gate_all[tr].float().mean())
    print("FLOORS:", json.dumps({"base": out["floor_base_policy"],
                                 "majority": out["floor_majority_class"]}, indent=1), flush=True)

    # ---- THE ARMS ---------------------------------------------------------
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        net = build_net(meta, args.ckpt, device)
        if arm == "heads":
            for p in net.policy.parameters():
                p.requires_grad_(False)
            params = list(net.gate.parameters())
            # the CARD head lives inside PolicyNet; unfreeze only it, never the cell head.
            card_head = getattr(net.policy, "card", None) or getattr(net.policy, "card_head", None)
            if card_head is None:
                raise SystemExit("could not find the card head on PolicyNet -- name it explicitly "
                                 "here rather than guessing, or the 'heads' arm is silently a "
                                 "gate-only arm and the card number below would be the base policy's")
            for p in card_head.parameters():
                p.requires_grad_(True)
            params += list(card_head.parameters())
        else:
            params = [p for p in net.parameters() if p.requires_grad]
        opt = torch.optim.Adam(params, lr=args.lr)
        net.train()
        rng = np.random.default_rng(0)
        for ep in range(args.epochs):
            perm = rng.permutation(tr)
            tot = 0.0
            for i in range(0, len(perm), args.batch):
                idx = np.sort(perm[i:i + args.batch])
                cq, gq, pm = forward_batch(net, z, idx, device, costs)
                tg_b = t_gate_all[idx].to(device)
                tc_b = t_card_all[idx].to(device)
                loss = F.cross_entropy(gq, tg_b)
                play = tg_b == 1
                if int(play.sum()):
                    # the card loss is masked to PLAYABLE cards, exactly as the decision is
                    logits = cq[play].masked_fill(~pm[play], _NEG)
                    loss = loss + F.cross_entropy(logits, tc_b[play])
                opt.zero_grad()
                loss.backward()
                opt.step()
                tot += float(loss) * len(idx)
            print(f"  [{arm}] epoch {ep+1}/{args.epochs} loss={tot/len(perm):.4f}", flush=True)
        net.eval()
        gates, cards = [], []
        with torch.no_grad():
            for i in range(0, len(te), 256):
                idx = te[i:i + 256]
                cq, gq, pm = forward_batch(net, z, idx, device, costs)
                g, c = decide(cq, gq, pm, tau)
                gates.append(g)
                cards.append(c)
        out[f"student_{arm}"] = agreement(torch.cat(gates), torch.cat(cards),
                                          t_gate_all[te], t_card_all[te])
        print(f"STUDENT[{arm}]: {json.dumps(out[f'student_{arm}'])}", flush=True)

    pathlib.Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n=== SUMMARY (held-out top-1 agreement with the teacher) ===")
    print(f"  majority-class WAIT  gate {out['floor_majority_class']['gate']:.4f}")
    b = out["floor_base_policy"]
    print(f"  base policy (FLOOR)  gate {b['gate']:.4f}  card {b['card_given_teacher_plays']:.4f}  "
          f"joint {b['joint']:.4f}")
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        s = out.get(f"student_{arm}")
        if s:
            print(f"  student [{arm:5s}]      gate {s['gate']:.4f}  card "
                  f"{s['card_given_teacher_plays']:.4f}  joint {s['joint']:.4f}")
    print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
