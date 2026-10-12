"""Independent artifact arithmetic and scope checks; optional synthetic pytest runner."""
import ast
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def verify():
    r=json.loads((HERE/'report.json').read_text(encoding='utf8'))
    assert r['selection']['included']==len(r['matches'])>0
    assert sum(r['selection']['excluded'].values())+len(r['matches'])==r['selection']['candidate_files']
    assert r['pro_coverage']['files']==len(r['pro_coverage']['pages'])
    assert r['pro_coverage']['usable_replays']*2==len(r['pro_matches'])
    assert r['pro_coverage']['usable_replays']==r['pro_coverage']['files'], r['pro_coverage']['errors']
    assert all(p['plays']==p['timeline'] for p in r['pro_coverage']['pages'])
    assert len(r['metric_support'])==13
    assert all(m['checkpoint'] and isinstance(m['fast_plays'],bool) for m in r['matches'])
    assert sum(m['early_terminal'] for m in r['matches'])==r['early_terminal']['n']
    plays=collections.Counter();by_match=collections.Counter();pro=collections.Counter();unknown_fields=0
    for fname,counter in [('plays.jsonl',plays),('pro_plays.jsonl',pro)]:
        with (HERE/fname).open(encoding='utf8') as f:
            for line in f:
                j=json.loads(line);t=j['tick'];expected='1x' if t<2400 else '2x' if t<4800 else '3x'
                assert 0<=t<6000 and j['phase']==expected
                counter[j['phase']]+=1
                if fname=='plays.jsonl':
                    assert j['confirmed']
                    by_match[j['match']]+=1
                    unknown_fields+=sum(k in j for k in ('opp_elixir_true_EVAL_ONLY','opponent_hand','opponent_deck'))
    assert unknown_fields==0
    for ph in ('1x','2x','3x'):
        s=r['bot']['all'][ph]
        assert s['samples']['placement_raw_alignment_tiles']['median']<0.05
        assert s['rates']['plays']['count']==plays[ph]
        assert r['pros']['all_decks']['all'][ph]['rates']['plays']['count']==pro[ph]
        seconds=sum(m['phases'][ph]['seconds'] for m in r['matches'])
        assert math.isclose(seconds,s['seconds'])
        for key,rate in s['rates'].items():
            expected=sum(m['phases'][ph]['counts'].get(key,0) for m in r['matches'])
            assert math.isclose(rate['count'],expected,abs_tol=1e-6),(ph,key)
            assert math.isclose(rate['per_minute'],expected*60/seconds,abs_tol=1e-6)
            if rate['n_matches']>1:
                assert rate['ci95'] is not None
                assert rate['ci95'][0]<=rate['per_minute']+1e-10<=rate['ci95'][1]+1e-10
        assert math.isclose(s['rates']['damage_taken']['count'],
                            s['rates'].get('damage_taken_spell_associated',{'count':0})['count']+
                            s['rates'].get('damage_taken_unattributed',{'count':0})['count'])
    for m in r['matches']:
        assert by_match[m['id']]==m['quality']['confirmed_gameplay_plays']
        assert all(m['phases'][ph]['seconds']<=maxsecs for ph,maxsecs in [('1x',120),('2x',120),('3x',60)])
    for sec,expected in [('119',0.356),('120',0.714),('239',0.714),('240',1.074)]:
        assert abs(r['boundary_1s_bins'][sec]['median']-expected)<0.01
    # Import whitelist proves no runtime modules, simulator or torch are invoked.
    tree=ast.parse((HERE/'phase_stats.py').read_text(encoding='utf8'))
    allowed={'__future__','argparse','bisect','collections','datetime','hashlib','html','json','math','pathlib','re','statistics','urllib','video_metrics'}
    imports={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports|={a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert imports<=allowed
    video_tree=ast.parse((HERE/'video_metrics.py').read_text(encoding='utf8'))
    video_imports={n.module.split('.')[0] for n in ast.walk(video_tree) if isinstance(n,ast.ImportFrom)}
    video_imports|={a.name.split('.')[0] for n in ast.walk(video_tree) if isinstance(n,ast.Import) for a in n.names}
    assert video_imports <= {'ast','bisect','collections','math','re','pathlib'}
    # Positive control: a forbidden runtime import is detected by the same check.
    bad=ast.parse('import torch')
    bad_imports={a.name.split('.')[0] for n in ast.walk(bad) if isinstance(n,ast.Import) for a in n.names}
    assert not bad_imports<=allowed
    verify_followup(r)
    print('ARTIFACTS_OK',len(r['matches']),'matches;',sum(plays.values()),'bot plays;',sum(pro.values()),'human plays')


def verify_followup(r):
    assert set(r['video_metrics']['support'])==set('abcdefgh')
    ice={'xbow','tesla','knight','icewizard','skeletons','log','tornado','rocket'}
    human_by_id={m['id']:m for m in r['pro_matches']}
    assert len(human_by_id)==len(r['pro_matches'])
    for m in r['pro_matches']:
        assert m['icebow_overlap']==len(set(m['observed_cards']) & ice)
        assert m['icebow_like']==(m['icebow_overlap']>=5)
        assert m['xbow_tesla']==({'xbow','tesla'} <= set(m['observed_cards']))
        for ph in ('1x','2x','3x'):
            c=m['phases'][ph]['counts']
            assert sum(c.get('xbow_class.'+k,0) for k in ('bridge','defensive','enemy_side','unavailable'))==c.get('cards.x-bow',0)+c.get('cards.xbow',0)
            assert sum(v for k,v in c.items() if k.startswith('xbow_cell.'))+c.get('xbow_class.unavailable',0)==c.get('cards.x-bow',0)+c.get('cards.xbow',0)
    comp=r['human_comparison']
    assert comp['icebow_like_n']==sum(m['icebow_like'] for m in r['pro_matches'])
    assert comp['xbow_tesla_n']==sum(m['xbow_tesla'] for m in r['pro_matches'])
    criterion='icebow_like' if comp['icebow_like_n']>=15 else 'xbow_tesla'
    assert comp['selected']==criterion
    assert set(comp['ids'])=={m['id'] for m in r['pro_matches'] if m[criterion]}
    assert comp['selected_n']==len(comp['ids'])
    # Reconcile every raw human placement independently of the parser helper.
    classes=collections.Counter(); raw_orientations=collections.Counter()
    with (HERE/'pro_plays.jsonl').open(encoding='utf8') as f:
        for line in f:
            p=json.loads(line)
            if p['x'] is not None:
                rotate=(p['side']=='t' and p['orientation']=='1') or (p['side']=='o' and p['orientation']=='0')
                assert math.isclose(p['x'],18-p['raw_x'] if rotate else p['raw_x'])
                assert math.isclose(p['y'],32-p['raw_y'] if rotate else p['raw_y'])
                raw_orientations[p['orientation']]+=1
            if p['card'] in ('x-bow','xbow'):
                cls='unavailable' if p['y'] is None else 'defensive' if p['y']>21 else 'bridge' if p['y']>=16 else 'enemy_side'
                classes[p['match'],p['phase'],cls]+=1
    assert set(raw_orientations)=={'0','1'}
    for m in r['pro_matches']:
        for ph in ('1x','2x','3x'):
            for cls in ('bridge','defensive','enemy_side','unavailable'):
                assert classes[m['id'],ph,cls]==m['phases'][ph]['counts'].get('xbow_class.'+cls,0)
    events=collections.defaultdict(list)
    with (HERE/'video_events.jsonl').open(encoding='utf8') as f:
        for line in f:
            e=json.loads(line);events[e['match']].append(e)
            assert e['phase']==('1x' if e['tick']<2400 else '2x' if e['tick']<4800 else '3x')
            assert 0<=e['tick']<6000
            assert not ({'opponent_hand','opponent_deck','opp_elixir_true_EVAL_ONLY'} & e.keys())
            if e['kind']=='pressure' and e['response']:
                assert 0<e['response_tick']-e['tick']<=120
            if e['kind']=='tank' and e['delay'] is not None:
                assert math.isclose(e['delay'],(e['tesla_tick']-e['tick'])/20)
                assert e['tesla_tick']<=e['end_tick']
            if e['kind']=='tank' and e['survives'] is not None:
                assert e['complete'] and e['tesla_key'] is not None
            if e['kind']=='cycle' and e['complete']:
                assert 0<e['tick']-e['enemy_tick']<=80 and e['empty'] is not None
            if e['kind']=='clump':
                assert e['bodies']==len(e['body_keys']) and (e['bodies']==0 or e['bodies']>=2)
            if e['kind']=='kill' and e['order']=='supports_first':
                assert max(x[1] for x in e['support_disappearances'])<=e['tank_disappearance'][0]
    groups={'bot':r['matches'],'humans':[human_by_id[i] for i in comp['ids']],
            'icebow_like_humans':[m for m in r['pro_matches'] if m['icebow_like']]}
    for m in r['matches']+r['pro_matches']:
        assert dict(collections.Counter(e['kind'] for e in events[m['id']]))==m['video_event_counts']
    # Independent numerator and exposure checks, including state/archetype
    # denominators and full-window damage selection, for every outcome/phase.
    direct={'cycle_candidates':('cycle',lambda e:1),
            'cycle_assessed':('cycle',lambda e:int(e['complete'])),
            'cycle_empty':('cycle',lambda e:int(e['complete'] and e['empty'])),
            'cycle_empty_elixir':('cycle',lambda e:e['cost'] if e['complete'] and e['empty'] else 0),
            'pressure_windows':('pressure',lambda e:1),
            'pressure_complete':('pressure',lambda e:int(e['complete'])),
            'pressure_responses':('pressure',lambda e:int(e['complete'] and e['response'])),
            'tank_crossings':('tank',lambda e:1),'tank_complete':('tank',lambda e:int(e['complete'])),
            'tank_tesla_response':('tank',lambda e:int(e['delay'] is not None)),
            'pull_placements':('pull',lambda e:1),
            'pull_centre':('pull',lambda e:int(e['placement']=='centre')),
            'pull_side':('pull',lambda e:int(e['placement']=='side')),
            'kill_pushes':('kill',lambda e:1),'kill_assessed':('kill',lambda e:int(e['complete'])),
            'kill_supports_first':('kill',lambda e:int(e['order']=='supports_first')),
            'clump_contacts':('clump',lambda e:1),'clump_episodes':('clump',lambda e:int(e['bodies']>=2)),
            'clump_bodies':('clump',lambda e:e['bodies']),
            'clump_elixir':('clump',lambda e:e['nominal_elixir']),
            'clump_unknown_values':('clump',lambda e:e['unknown_values'])}
    means={'cycle_elixir_at_play':('cycle','elixir',lambda e:e['complete'] and e['empty']),
           'pressure_elixir':('pressure','elixir',lambda e:e['complete']),
           'pressure_response_elixir':('pressure','response_elixir',lambda e:e['complete']),
           'pressure_response_fraction':('pressure','response',lambda e:e['complete']),
           'tank_tesla_delay':('tank','delay',lambda e:True),
           'tank_tesla_survival':('tank','survives',lambda e:True),
           'tank_preexisting_tesla':('tank','preexisting_tesla',lambda e:True),
           'pull_offset':('pull','offset',lambda e:True),'pull_inward_offset':('pull','inward_offset',lambda e:True),
           'kill_supports_first_fraction':('kill','supports_first',lambda e:e['complete'])}
    for group,ms in groups.items():
        for split,phases in r['video_metrics'][group].items():
            selected=[m for m in ms if split=='all' or (m['big_loss'] if split=='big_losses' else m['outcome']==split)]
            for ph,row in phases.items():
                rows=[m for m in selected if m['phases'][ph]['seconds']>0]
                es=[e for m in rows for e in events[m['id']] if e['phase']==ph]
                for key,s in row['metrics'].items():
                    den=sum(m['phases'][ph]['seconds'] for m in rows)/60
                    if key in direct:
                        kind,fn=direct[key];num=sum(fn(e) for e in es if e['kind']==kind)
                    elif key in means:
                        kind,field,pred=means[key];xs=[e[field] for e in es if e['kind']==kind and pred(e) and e[field] is not None]
                        num,den=sum(xs),len(xs)
                    elif key.startswith(('commit.','commit_full.','commit_damage.')):
                        prefix,state=key.split('.',1)
                        subset=[e for e in es if e['kind']=='commit' and e['state']==state and (prefix=='commit' or e['complete'])]
                        den=sum(m['video_exposure'][ph].get(state,0) for m in rows)/60
                        num=len(subset)
                        if prefix=='commit_damage':num,den=sum(e['damage_taken'] for e in subset),len(subset)
                    elif key.startswith(('xbow.','xbow_full.','xbow_damage.')):
                        prefix,arch=key.split('.',1)
                        subset=[e for e in es if e['kind']=='xbow' and e['archetype']==arch and (prefix=='xbow' or e['complete'])]
                        num=len(subset);den=sum(m['phases'][ph]['seconds'] for m in rows if m['opponent_archetype']==arch)/60
                        if prefix=='xbow_damage':num,den=sum(e['damage'] for e in subset),len(subset)
                    else:raise AssertionError('Unaudited metric '+key)
                    assert math.isclose(s['numerator'],num,abs_tol=1e-6),(group,split,ph,key,'numerator')
                    assert math.isclose(s['denominator'],den,abs_tol=1e-6),(group,split,ph,key,'denominator')
                    if den:
                        assert math.isclose(s['value'],num/den,abs_tol=1e-8)
                        if s['n_clusters']>1:assert s['ci95'] is not None
                        if s['ci95']:assert s['ci95'][0]-1e-8<=s['value']<=s['ci95'][1]+1e-8
                    else:assert s['value'] is None and s['ci95'] is None
    text=(HERE/'report.md').read_text(encoding='utf8')
    assert text.index('## Corrected human X-Bow placement')<text.index('## Video metrics')<text.index('## Previous-ticket')
    assert len(r['video_findings'])==10


if __name__=='__main__':
    if '--tests' in sys.argv:
        env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
        cmd=[str(ROOT/'icebow/.venv/Scripts/python.exe'),'-B','-m','pytest','-q','-p','no:cacheprovider',str(HERE/'test_phase_stats.py')]
        result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True)
        print(result.stdout,end='');print(result.stderr,end='')
        if result.returncode:raise SystemExit(result.returncode)
        print('SYNTHETIC_TESTS_OK')
    else:verify()
