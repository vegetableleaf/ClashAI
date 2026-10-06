"""Opt-in live companion for public_hand_belief_v2 checkpoints.

Existing owner processes and canonical live modules on disk are unchanged.
This class adds inputs, never overrides action choices or affordability logic.
"""
import threading
import torch
from . import live_gen
from .live_gen_v2 import GenPilot as AuditedPilot
from .model_hand_belief_v2 import load_checkpoint
from .opponent_hand_v2 import belief_tokens,belief_at

_loader_lock=threading.Lock()

class HandGenPilot(AuditedPilot):
    def __init__(self,*args,**kwargs):
        # The legacy pilot has no loader injection API. Restrict substitution to
        # synchronous initialization in this explicit opt-in process and restore.
        with _loader_lock:
            original=live_gen.load_model
            try:
                live_gen.load_model=load_checkpoint
                super().__init__(*args,**kwargs)
            finally:live_gen.load_model=original

    def row(self,frame):
        b,info=super().row(frame)
        if self.public is None:raise ValueError('Public observer must be initialized')
        # Current observed tick; never use projected future as a public event.
        tick=int(frame['game_tick'])
        features=belief_tokens(self.public.plays,tick,self.public.side,self.gid)
        for key,value in features.items():b[key]=torch.as_tensor(value,device=self.dev).unsqueeze(0)
        if self.public_audit:
            self._public_audit_snapshot=dict(self._public_audit_snapshot or {},
                opponent_hand_belief=belief_at(self.public.plays,tick,self.public.side),
                hand_information_enabled=self.model.hand_information_enabled,
                hand_tokens=features['opp_hand'].tolist(),hand_quality=features['opp_hand_quality'].tolist())
        return b,info
