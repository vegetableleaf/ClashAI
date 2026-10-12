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
    allowed={'__future__','argparse','bisect','collections','datetime','hashlib','html','json','math','pathlib','re','statistics','urllib'}
    imports={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports|={a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert imports<=allowed
    # Positive control: a forbidden runtime import is detected by the same check.
    bad=ast.parse('import torch')
    bad_imports={a.name.split('.')[0] for n in ast.walk(bad) if isinstance(n,ast.Import) for a in n.names}
    assert not bad_imports<=allowed
    print('ARTIFACTS_OK',len(r['matches']),'matches;',sum(plays.values()),'bot plays;',sum(pro.values()),'human plays')


if __name__=='__main__':
    if '--tests' in sys.argv:
        env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
        cmd=[str(ROOT/'icebow/.venv/Scripts/python.exe'),'-B','-m','pytest','-q','-p','no:cacheprovider',str(HERE/'test_phase_stats.py')]
        result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True)
        print(result.stdout,end='');print(result.stderr,end='')
        if result.returncode:raise SystemExit(result.returncode)
        print('SYNTHETIC_TESTS_OK')
    else:verify()
