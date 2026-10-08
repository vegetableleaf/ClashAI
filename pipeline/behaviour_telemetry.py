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
        frame['elixir']={int(p['side']):float(p['elixir_exact']) for p in raw.get('players',[])}
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
        # lead 2026-10-07: leak = share of time at >= 9.5 elixir (live_eval.py's pct_time_ge_9.5), per phase
        fr=[(f['tick'],f['elixir'][side]) for f in self.frames if side in f.get('elixir',{})]
        if len(fr)>1:
            leak={}
            for name,lo,hi in (('1x',0,2400),('2x',2400,3600),('OT',3600,10**9)):
                dts=[(min(b[0]-a[0],30),a[1]) for a,b in zip(fr,fr[1:]) if lo<=a[0]<hi]
                tot=sum(d for d,_ in dts)
                leak[name]=round(sum(d for d,e in dts if e>=9.5)/tot,4) if tot else None
            out['leak_ge_9_5']=leak
        # lead 2026-10-08: per-phase card counts and X-Bow class (lead rule defensive / reach lock), as the pro comparison
        from collections import Counter
        from .public_outcomes import label_recording
        ph=lambda t:'1x' if t<2400 else ('2x' if t<3600 else 'OT')
        cards={p:Counter() for p in ('1x','2x','OT')}
        for q in self.plays:
            if q['side']==side and not q['ability']:cards[ph(q['tick'])][q['card']]+=1
        out['phase_cards']={p:dict(c) for p,c in cards.items()}
        lab=label_recording(dict(frames=self.frames,log=self.plays,final=final or {}),normalized=True)
        xb={p:dict(n=0,defensive=0,offensive_lock=0) for p in ('1x','2x','OT')}
        for b in lab['xbows']:
            if b['side']!=side:continue
            d=xb[ph(b['tick'])];d['n']+=1;d['defensive']+=bool(b['defensive_xbow']);d['offensive_lock']+=bool(b['offensive_xbow'])
        out['xbow_phase']=xb
        out['tower_rockets_phase']={p:sum(1 for r in lab['rockets'] if r['side']==side and ph(r['tick'])==p and r.get('tower_rocket'))
                                    for p in ('1x','2x','OT')}
        return out
