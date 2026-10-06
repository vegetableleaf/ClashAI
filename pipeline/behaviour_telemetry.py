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

    def play(self, tick, side, card, x, y, ability=False, elixir=None):
        self.plays.append(dict(tick=int(tick),side=int(side),card=card,x=x,y=y,ability=ability,accepted=True,
                               **({} if elixir is None else {'elixir':float(elixir)})))

    def result(self, side, final=None):
        out=summarize(dict(frames=self.frames,log=self.plays,final=final or {}),side,normalized=True)
        # lead 2026-10-06: elixir economy per phase (1x < 2400 ticks <= 2x < 3600 <= OT) for OUR plays (cards only)
        mine=[q for q in self.plays if q['side']==side and not q['ability'] and 'elixir' in q]
        if mine:
            end=max([f['tick'] for f in self.frames]+[q['tick'] for q in mine])
            econ={}
            for name,lo,hi in (('1x',0,2400),('2x',2400,3600),('OT',3600,10**9)):
                ps=[q for q in mine if lo<=q['tick']<hi]
                dur=max(0,min(end,hi)-lo)/1200.0
                econ[name]=dict(plays=len(ps),minutes=round(dur,3),
                                elixir_at_play=round(sum(q['elixir'] for q in ps)/len(ps),3) if ps else None)
            out['economy']=econ
        return out
