"""Three small synthetic matches; no imports from runtime/training/pipeline."""
import io
import json
import phase_stats as ps
import video_metrics as vm


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


def test_human_orientation_and_xbow_partition_both_sides_all_phases():
    # Real HTML schema: data-i is shared by both sides, orientation changes
    # between replays. A blue/team label alone cannot identify the top edge.
    for orientation in ('0','1'):
        tags=[]
        for side in ('t','o'):
            rotate=(side=='t') == (orientation=='1')
            for tick, own_y in ((100,19.5),(2500,22.5),(4900,19.5)):
                raw_y=32-own_y if rotate else own_y
                tags.append(f'<div data-x="3500" data-y="{raw_y*1000}" data-c="x-bow" data-t="{tick}" data-s="{side}" data-i="{orientation}"></div>')
        tags.append('<div class="end_time" style="left:3000px;"></div>')
        class Fixture:
            stem='fixture'
            def read_bytes(self):return json.dumps({'payload':{'html':''.join(tags)}}).encode()
        rows,error,_=ps.analyse_pro(Fixture(),io.StringIO())
        assert error is None
        for m in rows:
            for ph in ps.PHASES:
                c=m['phases'][ph]['counts']
                assert sum(c['xbow_class.'+k] for k in ('bridge','defensive','enemy_side','unavailable'))==c['cards.x-bow']==1
                assert c['xbow_class.enemy_side']==0
            assert m['phases']['1x']['counts']['xbow_class.bridge']==1
            assert m['phases']['2x']['counts']['xbow_class.defensive']==1
    for y,expected in ((None,'unavailable'),(15.99,'enemy_side'),(16,'bridge'),(21,'bridge'),(21.01,'defensive')):
        assert ps.xbow_class(y)==expected
    assert ps.human_xy(dict(x=3.5,y=19.5,side='t',index=None))==(None,None)


def test_cohort_overlap_fallback_and_archetype_precedence():
    m=dict(last_tick=5000)
    own=[dict(card=c,tick=100,x=3.5,y=19.5) for c in ('x-bow','tesla','knight','the-log','skeletons')]
    vm.human(m,own,[],ps.ARCH_ORDER)
    assert m['icebow_like'] and m['icebow_overlap']==5 and m['xbow_tesla']
    vm.human(m,own[:4],[],ps.ARCH_ORDER)
    assert not m['icebow_like'] and m['xbow_tesla']
    assert vm.archetype(['MegaKnight','HogRider'],ps.ARCH_ORDER)=='Hog Rider'
    assert vm.archetype(['Xbow','Golem'],ps.ARCH_ORDER)=='X-Bow'
    assert vm.archetype(['unknown'],ps.ARCH_ORDER)=='Other'


def test_pressure_timing_other_lane_and_censoring():
    v=vm.new_video()
    own=[dict(tick=220,x=14.5,y=20,name='Knight'),dict(tick=300,x=3.5,y=20,name='Xbow')]
    enemy=[dict(tick=100,x=3.5,y=8),dict(tick=101,x=14.5,y=8),dict(tick=500,x=3.5,y=8),dict(tick=100,x=3.5,y=9)]
    vm.pressure(v,own,enemy,600)
    assert len(v['events'])==3
    assert v['events'][0]['response'] and v['events'][0]['complete']
    assert not v['events'][1]['response']  # Other-lane play is outside 6 seconds.
    assert not v['events'][2]['complete']
    assert not vm.covered([100,120,200,220],100,220)
    assert vm.covered(list(range(100,241,20)),100,220)


def video_fixture():
    cat={1:dict(display_name='Giant',type='troop',elixir=5,count=1),
         2:dict(display_name='Musketeer',type='troop',elixir=4,count=1),
         3:dict(display_name='Tesla',type='building',elixir=4,count=1),
         4:dict(display_name='Skeletons',type='troop',elixir=1,count=3)}
    ds=[state(t,7) for t in range(100,701,20)]
    def body(s,key,cid,x,y,own=False):
        s['bodies'].append(dict(address=key,card_id=cid,side=1 if own else 0,x=x*1000,y=y*1000,hp=100))
    for s in ds:
        t=s['tick']
        if 120<=t<=240:body(s,'tank',1,3.5,15 if t==120 else 17)
        if 120<=t<=180:body(s,'support',2,3.5,14)
        if t>=180:body(s,'tesla',3,7.5,22,True)
        if 160<=t<=260:body(s,'skel',4,14.5,25,True)
    plays=[dict(name='Tesla',tick=160,x=7.5,y=22,cost=4,elixir_public_before=7),
           dict(name='Skeletons',tick=140,x=14.5,y=25,cost=1,elixir_public_before=7),
           dict(name='Knight',tick=180,x=7.5,y=22,cost=3,elixir_public_before=7),
           dict(name='Xbow',tick=200,x=3.5,y=19.5,cost=6,elixir_public_before=7,xbow_class='bridge')]
    m=dict(id='fixture',phases={p:ps.blank_phase() for p in ps.PHASES},outcome='wins',big_loss=False)
    m['phases']['1x']['seconds']=30
    vm.bot(m,ds,[ps.units(s,cat) for s in ds],plays,[dict(tick=300,amount=400,role='dealt'),dict(tick=300,amount=100,role='taken')],[],cat,ps.ARCH_ORDER,ps.towers,ps.own_xy,ps.in_spell)
    return m,ds,cat,plays


def test_cycle_pull_kill_tesla_survival_and_damage_receipts():
    m,_,_,_=video_fixture(); events=m['video']['events']
    cycle=next(e for e in events if e['kind']=='cycle')
    assert cycle['complete'] and cycle['empty'] and cycle['cost']==1
    pull=next(e for e in events if e['kind']=='pull' and e['card']=='Knight')
    assert pull['placement']=='centre' and pull['offset']==4
    tank=next(e for e in events if e['kind']=='tank')
    assert tank['delay']==1 and tank['survives'] and tank['complete']
    kill=next(e for e in events if e['kind']=='kill')
    assert kill['order']=='supports_first' and kill['complete']
    bow=next(e for e in events if e['kind']=='xbow')
    assert bow['damage']==400 and bow['complete'] and bow['archetype']=='Giant'
    commit=next(e for e in events if e['kind']=='commit')
    assert commit['state']=='level' and commit['damage_taken']==100


def test_censored_cycle_tesla_kill_and_no_fake_crossing():
    m,ds,cat,plays=video_fixture()
    ds=ds[:7]  # End before full cycle observation and push closure.
    vm.bot(m,ds,[ps.units(s,cat) for s in ds],plays,[],[],cat,ps.ARCH_ORDER,ps.towers,ps.own_xy,ps.in_spell)
    ev=m['video']['events']
    assert not next(e for e in ev if e['kind']=='cycle')['complete']
    assert next(e for e in ev if e['kind']=='tank')['survives'] is None
    assert next(e for e in ev if e['kind']=='kill')['order']=='censored'
    ds=ds[2:] # Starts with tank already across bridge.
    vm.bot(m,ds,[ps.units(s,cat) for s in ds],[],[],[],cat,ps.ARCH_ORDER,ps.towers,ps.own_xy,ps.in_spell)
    assert not any(e['kind']=='tank' for e in m['video']['events'])


def test_spell_clump_uses_simultaneous_units_inside_enemy_footprint():
    m,ds,cat,_=video_fixture()
    cat[5]=dict(display_name='Fireball',type='spell',elixir=4,count=1)
    for s in ds:
        if s['tick']==200:
            s['projectiles']=[dict(card_id=5,side=0,target_x=3500,target_y=25500)]
            for key,x in [('a',3.5),('b',5),('outside',10)]:
                s['bodies'].append(dict(address=key,card_id=3,side=1,x=x*1000,y=25500,hp=100))
    episodes=[dict(name='Fireball',tower='own_left',tick=200,last_tick=200)]
    vm.bot(m,ds,[ps.units(s,cat) for s in ds],[],[],episodes,cat,ps.ARCH_ORDER,ps.towers,ps.own_xy,ps.in_spell)
    e=next(e for e in m['video']['events'] if e['kind']=='clump')
    assert e['bodies']==2 and e['nominal_elixir']==8


def test_state_exposure_cluster_denominators_and_fraction_ci():
    m,_,_,_=video_fixture()
    assert vm.state_label({'own_left':2001,'enemy_left':1000})=='ahead'
    assert vm.state_label({'own_left':0,'enemy_left':1000})=='level'
    assert vm.state_label({'own_left':0,'enemy_left':1001})=='behind'
    r=vm.summarize([m])['all']['1x']['metrics']
    assert r['commit.level']['denominator']==.5 and r['commit.level']['value']==2
    assert r['xbow.Giant']['denominator']==.5
    s=vm.estimate([(0,10),(0,20)],'fraction')
    assert s['ci95'][1]>0 and s['n']==30 and s['n_clusters']==2
    assert vm.estimate([], 'rate')['value'] is None


def test_tesla_after_observation_gap_is_not_a_response_to_earlier_push():
    m,ds,cat,plays=video_fixture()
    ds=ds[:3]+ds[10:]
    plays=[dict(name='Tesla',tick=320,x=7.5,y=22,cost=4,elixir_public_before=7)]
    vm.bot(m,ds,[ps.units(s,cat) for s in ds],plays,[],[],cat,ps.ARCH_ORDER,ps.towers,ps.own_xy,ps.in_spell)
    e=next(e for e in m['video']['events'] if e['kind']=='tank')
    assert e['end_tick']==140 and not e['complete']
    assert e['delay'] is None and e['tesla_tick'] is None
