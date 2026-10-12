"""Three small synthetic matches; no imports from runtime/training/pipeline."""
import io
import json
import phase_stats as ps


def state(tick, elixir, enemy_y=None, side=1):
    bodies=[]
    for s in (0,1):
        for x,y,hp in ((3500,6500,4424),(14500,6500,4424),(9000,3000,7032)):
            bodies.append(dict(side=s,x=x,y=y if s==0 else 32000-y,card_id=-1,hp=hp,max_hp=hp))
    if enemy_y is not None:
        x,y=(3500,enemy_y) if side==1 else (14500,32000-enemy_y)
        bodies.append(dict(side=1-side,x=x,y=y,card_id=26000000,hp=100,max_hp=100,address='enemy_knight'))
    return dict(tick=tick,side=side,elixir=elixir,bodies=bodies,projectiles=[],t_dev=tick/20,
                hand=[dict(name='Xbow',cost=6),dict(name='Knight',cost=3)])


CAT={26000000:dict(display_name='Knight',elixir=3,count=1,type='troop')}


def test_match_crosses_phase_boundaries_and_excludes_tiebreak():
    states=[state(t,5) for t in (2399,2400,4799,4800,5999,6000,6100)]
    assert [ps.phase(s['tick']) for s in states]==['1x','2x','2x','3x','3x',None,None]
    assert list(ps.slices(2390,4810))==[('1x',2390,2400),('2x',2400,4800),('3x',4800,4810)]
    # Huge tiebreak HP drain must not enter combat damage totals.
    states[-1]['bodies'][0]['hp']=0
    # Unknown moving body with -1 must not overwrite a tower's HP.
    states[1]['bodies'].append(dict(card_id=-1,side=0,x=3500,y=14000,hp=12,max_hp=100,address='unknown'))
    data=dict(decisions=states,frames=[],plays=[],confirmations=[],abilities=[],head={},sha256='synthetic',bytes=0,errors=0)
    m=ps.analyse_live('synthetic',data,CAT,{},io.StringIO(),io.StringIO(),io.StringIO())
    assert sum(s['counts']['damage_dealt'] for s in m['phases'].values())==0


def test_match_crossing_samples_own_elixir_and_response_trade():
    states=[state(100,7,15000),state(110,2.5,17000),state(120,2.8,18000),state(150,3),state(180,4)]
    us=[ps.units(s,CAT) for s in states]
    pushes,_=ps.push_crossings(states,us)
    assert len(pushes)==1
    assert pushes[0]['tick']==110 and pushes[0]['elixir']==2.5
    assert pushes[0]['crossing_interval_seconds']==0.5
    assert pushes[0]['closed']
    assert ps.trade_sign(5,3)==('positive',2)
    assert ps.trade_sign(3,6)==('negative',-3)
    assert ps.trade_sign(3,3)==('even',0)
    # An actual matched, confirmed response contributes once to the defence.
    data=dict(decisions=states,frames=[],plays=[dict(tick=120,name='Knight',xy=[1-3.5/18,22/32],elixir=2.8)],
              confirmations=[dict(tick=130,name='Knight',spawn=[[1-3.5/18,22/32]])],abilities=[],head={},sha256='test',bytes=0,errors=0)
    push_out=io.StringIO()
    ps.analyse_live('synthetic',data,CAT,{},io.StringIO(),push_out,io.StringIO())
    row=json.loads(push_out.getvalue())
    assert row['response_seconds']==0.5 and row['own_spent']==3
    assert row['trade_sign_proxy']=='even'


def test_mirrored_match_intrusions_and_confirmation_are_not_double_counted():
    states=[state(100,8,15000,0),state(120,4,17000,0),state(140,5,18000,0)]
    pushes,_=ps.push_crossings(states,[ps.units(s,CAT) for s in states])
    assert len(pushes)==1 and pushes[0]['elixir']==4 and pushes[0]['lane']=='left'
    intrusion=[state(100,7,17000),state(120,8,18000)]
    assert ps.push_crossings(intrusion,[ps.units(s,CAT) for s in intrusion])[0]==[]
    plays=[dict(tick=100,name='Knight'),dict(tick=120,name='Knight')]
    matched=ps.match_plays(dict(plays=plays,confirmations=[dict(tick=125,name='Knight',spawn=[[0.5,0.7]])]))
    assert [p['confirmed'] for p in matched]==[False,True]
    parser=ps.ReplayHTML()
    parser.feed('<div class="marker end_time" style="left:1800px;"></div>'
                '<div data-x="3500" data-y="12500" data-c="x-bow" data-t="2399" data-s="t"></div>'
                '<div data-x="None" data-y="None" data-c="_invalid" data-t="2401" data-s="t"></div>')
    assert parser.end_seconds==180 and parser.plays[0]['tick']==2399
    assert parser.plays[1]['x'] is None
