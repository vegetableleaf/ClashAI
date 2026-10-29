"""OPP-LEARN-C: strip_ckpt.py IN.pt OUT.pt -- an rl_royale opp-learner checkpoint without its optimizer / RL state (the "rl"
key: Adam moments etc., ~90 MB of a 135 MB file), for copying to the eval pod. The weights and every meta key
(opp / opp_sim / memory / card_vocab / args ...) are kept, so e1_eval.load_policy plays it unchanged. Prints both sha256s."""
import hashlib
import sys

import torch

src, dst = sys.argv[1], sys.argv[2]
ck = torch.load(src, map_location="cpu", weights_only=False)
ck.pop("rl", None)
torch.save(ck, dst)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]   # noqa: E731
print(src, sha(src), "->", dst, sha(dst), sorted(ck))
