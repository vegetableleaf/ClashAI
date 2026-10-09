"""MEASUREMENT ONLY, VM tree ~/rocket_dead/repo (never ~/ClashBot, never main): after vm_setup.sh copied the push-Rocket
telemetry (~/pipeline_plays/tel: behaviour_telemetry.py + push_refine.py), add 'lr_rockets' to BehaviourTelemetry.result:
one row per accepted Rocket of ``side`` = [tick, x, y (my board frame, tiles; enemy at the top), enemy K/L/R alive,
enemy bodies within 2.5 tiles at the play tick, at the impact tick (flight 0.35 tiles/tick from my king)].
    ~/venv/bin/python vm_tel_patch.py ~/rocket_dead/repo/pipeline"""
import pathlib, sys

P = pathlib.Path(sys.argv[1]) / 'behaviour_telemetry.py'
t = P.read_text()
OLD = "        out['push']=push_metrics(self.frames,self.plays,side)\n        return out"
NEW = """        out['push']=push_metrics(self.frames,self.plays,side)
        # L74 rocket_dead: my Rockets with the enemy tower states and nearby enemy bodies (my board frame, tiles)
        import bisect, math
        from .dataset_gen import card_key
        ticks=[f['tick'] for f in self.frames]; rs=[]
        mx=(lambda x:x/1000) if side==0 else (lambda x:18-x/1000)
        my=(lambda y:32-y/1000) if side==0 else (lambda y:y/1000)
        def near(i,X,Y):
            return sum(1 for b in self.frames[i]['bodies'] if b['side']!=side and b['hp']>0 and b.get('card')!='rocket'
                       and math.hypot(mx(b['x'])-X,my(b['y'])-Y)<=2.5)
        for q in self.plays:
            if q['side']!=side or q['ability'] or q.get('x') is None or card_key(q['card'])!='rocket':continue
            i=bisect.bisect_right(ticks,q['tick'])-1
            if i<0:continue
            X,Y=mx(q['x']),my(q['y'])
            alive={'K':False,'L':False,'R':False}
            for tw in self.frames[i]['towers']:
                if tw['side']!=side and tw['hp']>0:alive['K' if tw['kind']=='king' else ('L' if mx(tw['x'])<9 else 'R')]=True
            j=max(0,bisect.bisect_right(ticks,q['tick']+math.hypot(X-9,Y-29)/0.35)-1)
            rs.append([q['tick'],round(X,3),round(Y,3),alive['K'],alive['L'],alive['R'],near(i,X,Y),near(j,X,Y)])
        out['lr_rockets']=rs
        return out"""
if NEW not in t:
    assert t.count(OLD) == 1, 'unexpected behaviour_telemetry.py'
    P.write_text(t.replace(OLD, NEW))
print('patched', P)
