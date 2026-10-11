"""Small event transformer with a zero-initialized gated trunk residual."""
import math
import torch
from torch import nn


class HistoryEncoder(nn.Module):
    def __init__(self, trunk_d, n_cards, cap=256, width=64, layers=2, heads=4):
        super().__init__()
        if min(cap, width, layers, heads) <= 0 or width % heads:
            raise ValueError('invalid history architecture')
        self.cap = int(cap)
        self.register_buffer('cfg', torch.tensor([cap, width, layers, heads]))
        self.card = nn.Embedding(n_cards, width)
        self.kind = nn.Embedding(6, width)
        self.side = nn.Embedding(2, width)
        self.form = nn.Embedding(4, width)
        self.numeric = nn.Linear(6, width)
        self.position = nn.Embedding(cap, width)
        self.encoder = nn.TransformerEncoder(nn.TransformerEncoderLayer(
            width, heads, dim_feedforward=width*2, dropout=0, batch_first=True,
            activation='gelu'), layers, enable_nested_tensor=False)
        self.out = nn.Linear(width, trunk_d)
        self.gate = nn.Parameter(torch.zeros(trunk_d))
        self.zero_history = False  # ablation zeros inputs, retains every learned weight

    def forward(self, events):
        if events.ndim != 3 or events.shape[1] != self.cap or events.shape[2] != 10:
            raise ValueError(f'expected history [B,{self.cap},10]')
        if self.zero_history:
            events = torch.zeros_like(events)
        mask = events[..., 0] > 0
        numeric = events[..., 4:].clone()
        numeric[..., 2] /= 360.0
        x = (self.card(events[..., 2].long()) + self.kind(events[..., 0].long()) +
             self.side(events[..., 1].long()) + self.form(events[..., 3].long()) + self.numeric(numeric))
        pos = torch.arange(self.cap, device=x.device)
        x = x + self.position(pos)[None]
        # Continuous Fourier time encoding preserves elapsed time between events.
        freq = torch.exp(torch.arange(0, x.shape[-1], 2, device=x.device)*(-math.log(10000)/x.shape[-1]))
        phase = events[..., 6:7]*freq
        timing = torch.stack((phase.sin(), phase.cos()), -1).flatten(-2)[..., :x.shape[-1]]
        x = x + timing
        safe = mask.clone()
        safe[:, 0] = True  # empty histories must never cause all-masked attention NaNs
        x = self.encoder(x, src_key_padding_mask=~safe)
        pooled = (x*mask.unsqueeze(-1)).sum(1)/mask.sum(1, keepdim=True).clamp(min=1)
        return self.out(pooled) * self.gate.tanh() * mask.any(1, keepdim=True)
