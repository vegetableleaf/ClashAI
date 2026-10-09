"""MEASUREMENT ONLY, VM tree ~/deadlane/repo (never ~/ClashBot, never main): after vm_setup.sh copied the push-Rocket
telemetry (~/pipeline_plays/tel: behaviour_telemetry.py + push_refine.py), add 'lr_xbows' to BehaviourTelemetry.result:
one row per accepted X-Bow of ``side`` = [tick, x, y (my board frame, tiles; enemy towers at the top), enemy L alive,
enemy R alive] from the last frame at or before the play tick.  ~/venv/bin/python vm_tel_patch.py ~/deadlane/repo/pipeline"""
import pathlib, sys

P = pathlib.Path(sys.argv[1]) / 'behaviour_telemetry.py'
t = P.read_text()
OLD = "        out['push']=push_metrics(self.frames,self.plays,side)\n        return out"
NEW = """        out['push']=push_metrics(self.frames,self.plays,side)
        # L74 deadlane: my X-Bows with the enemy princess states at the play (my frame)
        import bisect
        from .dataset_gen import card_key
        ticks=[f['tick'] for f in self.frames]; xs=[]
        for q in self.plays:
            if q['side']!=side or q['ability'] or q.get('x') is None or card_key(q['card'])!='x-bow':continue
            i=bisect.bisect_right(ticks,q['tick'])-1
            if i<0:continue
            mx=(lambda x:x/18000) if side==0 else (lambda x:1-x/18000)
            alive={'L':False,'R':False}
            for tw in self.frames[i]['towers']:
                if tw['side']!=side and tw['kind']=='princess' and tw['hp']>0:alive['L' if mx(tw['x'])<.5 else 'R']=True
            xs.append([q['tick'],round(mx(q['x'])*18,3),round((1-q['y']/32000 if side==0 else q['y']/32000)*32,3),alive['L'],alive['R']])
        out['lr_xbows']=xs
        return out"""
if NEW not in t:
    assert t.count(OLD) == 1, 'unexpected behaviour_telemetry.py'
    P.write_text(t.replace(OLD, NEW))
print('patched', P)
