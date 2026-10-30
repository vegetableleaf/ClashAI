"""LEARNER-SPEED ticket A (``split_attn``, learner-only, opt-in): nn.MultiheadAttention's training path without the packed
in_proj's select glue.

torch's slow path (F.multi_head_attention_forward -> _in_projection_packed) runs ONE packed q/k/v matmul, then copies the
result into a contiguous [3, L, B, E] buffer and selects q / k / v from it. In the backward each select zero-fills a full
[3, L, B, E] gradient buffer, the three are summed and the transpose chain copies once more (SCALE.md 7b: 986M zero-filled
elements per 1,024-row step in the trunk, 152M in the memory encoder, ~25% of the step's kernel time).

``SplitMHA.forward`` (grad enabled, self-attention, batch_first, need_weights False, no attn_mask / causal / bias_k /
zero_attn) runs the SAME packed matmul with the same weights and the same SDPA call; only the split is views (unbind) of
the matmul's output, whose backward is one stack. Sums of exact zeros are exact, so the packed gradient is the same
concatenation as torch's; expected bit-identical (tests: pipeline/tests/test_learner_attn.py). Anything else (no grad =
every actor / ref / anchor / live forward, other arguments) calls nn.MultiheadAttention.forward unchanged.

Nothing on the actor or live path imports this file: ``use_split_attn(model)`` is called by rl_royale's Learner only.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class SplitMHA(nn.MultiheadAttention):
    def forward(self, query, key, value, key_padding_mask=None, need_weights=True, attn_mask=None,
                average_attn_weights=True, is_causal=False):
        if (not torch.is_grad_enabled() or need_weights or attn_mask is not None or is_causal
                or query is not key or key is not value or query.dim() != 3 or not self.batch_first
                or not self._qkv_same_embed_dim or self.bias_k is not None or self.add_zero_attn or query.is_nested):
            return super().forward(query, key, value, key_padding_mask=key_padding_mask, need_weights=need_weights,
                                   attn_mask=attn_mask, average_attn_weights=average_attn_weights, is_causal=is_causal)
        kpm = F._canonical_mask(mask=key_padding_mask, mask_name="key_padding_mask", other_type=None,
                                other_name="attn_mask", target_type=query.dtype)
        x = query.transpose(1, 0)                                          # [L, B, E], as MHA's batch_first slow path
        L, B, E = x.shape
        H = self.num_heads
        proj = F.linear(x, self.in_proj_weight, self.in_proj_bias)         # the packed matmul (_in_projection_packed)
        q, k, v = (t.unflatten(-1, (H, E // H)).permute(1, 2, 0, 3) for t in proj.unflatten(-1, (3, E)).unbind(-2))
        mask = None
        if kpm is not None:                                                # multi_head_attention_forward's merge, verbatim
            mask = kpm.view(B, 1, 1, L).expand(-1, H, -1, -1).reshape(B * H, 1, L).view(B, H, -1, L)
        o = F.scaled_dot_product_attention(q, k, v, mask, self.dropout if self.training else 0.0, False)
        o = o.permute(2, 0, 1, 3).contiguous().view(B * L, E)
        o = F.linear(o, self.out_proj.weight, self.out_proj.bias).view(L, B, E)
        return o.transpose(1, 0), None


def use_split_attn(model: nn.Module) -> int:
    """Swap every plain nn.MultiheadAttention in ``model`` to SplitMHA in place (same parameters, buffers and state_dict
    keys; deepcopy keeps the class). -> the number swapped."""
    n = 0
    for m in model.modules():
        if type(m) is nn.MultiheadAttention:
            m.__class__ = SplitMHA
            n += 1
    return n
