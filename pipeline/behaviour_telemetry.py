"""Opt-in per-tick public acceptance recorder. Does not feed policies."""
from .public_outcomes import normalize, summarize
from .projectile_observation import sim_objects

class BehaviourTelemetry:
    def __init__(self):
        self.frames=[]
        self.plays=[]

    def __deepcopy__(self, memo):
        # Search forks disable telemetry immediately after copying env state.
        return BehaviourTelemetry()

    def observe(self, env):
        from .royale_env import SCALE
        raw=env.raw()
        raw.update(sim_objects(env.core.state(),env.names,SCALE))
        frame=normalize(raw,source='sim')
        if self.frames and self.frames[-1]['tick']==frame['tick']:self.frames[-1]=frame
        else:self.frames.append(frame)

    def play(self, tick, side, card, x, y, ability=False):
        self.plays.append(dict(tick=int(tick),side=int(side),card=card,x=x,y=y,ability=ability,accepted=True))

    def result(self, side, final=None):
        return summarize(dict(frames=self.frames,log=self.plays,final=final or {}),side,normalized=True)
