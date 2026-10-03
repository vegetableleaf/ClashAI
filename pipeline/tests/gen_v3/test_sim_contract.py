"""Actual RoyaleSim CPU replay versus the recording adapter. No policy or training."""
import numpy as np
import pytest
import json
from pathlib import Path
from pipeline import dataset_gen as D, obs_contract as O, dataset as DS
from pipeline import e1_eval as E
from pipeline.model_gen import GenModel
from pipeline.tests.test_rl_gen import _cfg


def test_royalesim_replay_forms_and_opponent_history_both_sides():
    pytest.importorskip("royalegym")
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline import policy_io as EP
    names=["Knight@evolution","Tesla@evolution","MiniPekka@hero","Skeletons","IceSpirits","Zap","Log","Arrows"]
    env=RoyaleSelfPlayEnv(forms_mode="deck",tail_cap=2400,feature_version=3)
    raw=env.reset(names,names,seed=0)
    pol=E.GenPolicy(GenModel(d=16,layers=1,d_c=8,n_cards=9,feature_version=3).eval(),
                    ['<pad>']+[D.card_key(n) for n in names])
    sides=[E.SelfPlaySide(env,names,s,'parity',0,_cfg(record=False),pol) for s in (0,1)]
    sim_rows=[]
    rec={"final_decks":{str(s):names for s in (0,1)},"log":[],"frames":[],"play_frames":[],
         "entity_fields":["side","x","y","name","hp","max_hp","kind","entity_id"]}
    truths=[];public=[];cost=env.costs(0)
    for tick in range(90,2400,20):
        raw=env.advance_to(tick)
        rows=[]
        for s in sides:
            s.state=raw;s.prepare();rows.append(s.gen_row(pol))
        sim_rows.append(rows)
        truths.append(raw)
        compact=EP.compact_raw(raw)
        fr=dict(tick=tick,elixir=[p["elixir_exact"] for p in raw["players"]],towers=[],
                entities=[[e["side"],e["x"],e["y"],e["name"],e["hp"],e["max_hp"],e["kind"],e["entity_id"]]
                          for e in raw["entities"]])
        rec["frames"].append(fr)
        for side in (0,1):
            p=env.core.state().players[side]
            hand=[env.deck_ids[side].index(c) for c in p.hand if c in env.deck_ids[side]]
            affordable=[i for i in hand if cost[i]*1000<=p.elixir_milli]
            if not affordable:
                continue
            i=min(affordable,key=lambda i: (-10 if i==0 else -5 if i==2 else cost[i]))
            cid=env.deck_ids[side][i]
            actual=2 if env.loaded_forms[side][i]==2 else int(any(v[0]==cid and v[2] for v in p.evo))
            x,y=3500,(7500 if side==0 else 24500)
            result=env.act(side,i,x,y)
            if result["accepted"]:
                event=dict(tick=tick,play_index=len(rec["log"]),side=side,card=D.card_key(names[i]),
                           x=x,y=y,accepted=True)
                rec["log"].append(event)
                public.append(dict(event,form=actual))
    inferred=D.played_forms(rec)
    assert public == env.public_plays or [dict(p,card=D.card_key(p['card'])) for p in env.public_plays] == public
    assert [p["form"] for p in inferred] == [p["form"] for p in public]
    tagged=D.tag_recording(rec,inferred,{})
    seen=set()
    gid={D.card_key(n):i+1 for i,n in enumerate(names)}
    for raw,fr,rows in zip(truths,tagged["frames"],sim_rows):
        for side in (0,1):
            deck=D.side_deck(names)
            train=O.from_engine(DS._as_compact(fr),side,deck,unmapped=set(),feature_version=3)
            sf,tf=rows[side]['unit_form'],O.to_unit_forms(train)
            np.testing.assert_array_equal(sf,tf,err_msg=f"tick={raw['tick']} side={side}")
            seen.update(sf.tolist())
            np.testing.assert_array_equal(D.opponent_past(inferred,raw["tick"],side,gid),rows[side]['opp_past'])
    assert seen == {0,1,2}
    forms=np.concatenate([r['unit_form'][r['mask']] for rows in sim_rows for r in rows])
    summary=dict(states=len(truths),side_views=2*len(truths),accepted_plays=len(public),
                 unit_tokens=len(forms),evolved=int((forms==1).sum()),hero=int((forms==2).sum()),
                 played_forms=sorted({p['form'] for p in public}),parity='exact')
    (Path(__file__).parent/'sim_parity_result.json').write_text(json.dumps(summary,indent=2))
