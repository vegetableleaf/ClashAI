"""MEASUREMENT ONLY, VM tree ~/threat/repo (never ~/ClashBot): add 'threat' to BehaviourTelemetry.result (per-tick
frames): my crown-tower HP at the first / last frame, and damage EPISODES = a tick where my towers' summed HP fell
with no fall in the previous 40 ticks (2 s) -> [episode tick, ticks to my first card play at or after it (None =
none before the end; play ticks as the telemetry logs them), my elixir at the episode tick].
    ~/venv/bin/python vm_threat_patch.py ~/threat/repo/pipeline"""
import pathlib, sys

P = pathlib.Path(sys.argv[1]) / 'behaviour_telemetry.py'
t = P.read_text()
OLD = "        out['push']=push_metrics(self.frames,self.plays,side)\n        return out"
NEW = """        out['push']=push_metrics(self.frames,self.plays,side)
        # L74 threat: my tower HP lost; damage episodes and the time to my first card play after each
        import bisect
        hs=[(f['tick'],sum(max(0,tw['hp']) for tw in f['towers'] if tw['side']==side),f.get('elixir',{}).get(side))
            for f in self.frames]
        mt=sorted(q['tick'] for q in self.plays if q['side']==side and not q['ability'])
        eps=[];last=-10**9
        for (t0,h0,_),(t1,h1,e1) in zip(hs,hs[1:]):
            if h1<h0:
                if t1-last>40:eps.append((t1,e1))
                last=t1
        ep=[]
        for tk,e in eps:
            i=bisect.bisect_left(mt,tk)
            ep.append([tk,(mt[i]-tk) if i<len(mt) else None,None if e is None else round(e,2)])
        out['threat']=dict(hp_start=hs[0][1] if hs else None,hp_end=hs[-1][1] if hs else None,episodes=ep)
        return out"""
if NEW not in t:
    assert t.count(OLD) == 1, 'unexpected behaviour_telemetry.py'
    P.write_text(t.replace(OLD, NEW))
print('patched', P)
