"""Did the distillation TERM actually move the card head? A mechanism check, not an outcome check.

Winrate on this project carries a seed-level sd of 5-10pp, so a 3pp training effect needs ~32 seeds
per arm to see. Agreement with the teacher is far quieter, and it answers the prior question: if the
distilled arms' card head does not sit closer to the teacher than the control's, the term is not
taking at all and no amount of winrate sampling is worth spending.

    python distill_agreement.py --corpus <npz> --ckpt a.pt b.pt ...

/!\ IN-SAMPLE for any arm that trained on this corpus. A HIGHER number is therefore not proof of
generalisation -- it is proof the term had an effect. To separate memorisation from learning, point
--corpus at a corpus labelled from seeds no arm trained on.
"""
import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import importlib.util

_spec = importlib.util.spec_from_file_location("distill_student", _HERE / "distill_student.py")
DS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DS)

import numpy as np
import torch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--ckpt", nargs="+", required=True)
    ap.add_argument("--batch", type=int, default=512)
    a = ap.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("export PYTHONHASHSEED=0 first (rollout_search's own setdefault is a no-op)")

    z, meta = DS.load_corpus(a.corpus)
    dev = torch.device("cpu")
    # `card_elixir`, the same key distill_student.py reads. The mask is rebuilt from the CORPUS,
    # not from this deck's config: a config edit since labelling would change which cards were
    # maskable and the agreement numbers would no longer be comparable across checkpoints.
    costs = torch.tensor(meta["card_elixir"], dtype=torch.float32, device=dev)
    t_gate = torch.as_tensor(np.asarray(z["teach_gate"]).astype(np.int64))
    t_card = torch.as_tensor(np.asarray(z["teach_card"]).astype(np.int64))
    tau = float(meta.get("gate_tau", 0.25))

    print(f"corpus {Path(a.corpus).name}: {len(t_gate)} rows, "
          f"{int((t_card >= 0).sum())} teacher-play rows\n")
    print(f"{'checkpoint':<22}{'gate':>8}{'card|plays':>12}{'joint':>8}")
    for ck in a.ckpt:
        net = DS.build_net(meta, ck, dev)
        net.eval()
        G, C = [], []
        with torch.no_grad():
            for s in range(0, len(t_gate), a.batch):
                idx = np.arange(s, min(s + a.batch, len(t_gate)))
                cq, gq, pm = DS.forward_batch(net, z, idx, dev, costs)
                g, c = DS.decide(cq, gq, pm, tau)
                G.append(g); C.append(c)
        g = torch.cat(G); c = torch.cat(C)
        r = DS.agreement(g, c, t_gate, t_card)
        print(f"{Path(ck).stem:<22}{r['gate']:>8.4f}{r['card_given_teacher_plays']:>12.4f}{r['joint']:>8.4f}")


if __name__ == "__main__":
    main()
