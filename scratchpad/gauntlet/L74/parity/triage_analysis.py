"""Reproducible offline v2 triage and v3 re-planning; standard library, no SIM."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity.core import Tracks, ps, mean
from scratchpad.gauntlet.L74.parity.planning import plan
from scratchpad.gauntlet.L74.parity.inference import role_limits

DEFAULT_RESULTS = Path('C:/Users/benpe/pod_backup_weekend/podD/x_PARITY_v2/results/PARITY_v2')
AGE_BINS = ['0-2 s', '2-5 s', '5-10 s', '>10 s']
TIME_BINS = ['0-30 s', '30-60 s', '60-120 s', '120-180 s', '180+ s']


def age_bin(ticks):
    return AGE_BINS[0 if ticks < 40 else 1 if ticks < 100 else 2 if ticks <= 200 else 3]


def time_bin(ticks):
    return TIME_BINS[0 if ticks < 600 else 1 if ticks < 1200 else 2 if ticks < 2400 else 3 if ticks < 3600 else 4]


class Aggregate:
    def __init__(self):
        self.counts=Counter(); self.position=[]; self.hp=[]; self.tower=[]

    def add(self, row):
        if row['tower']:
            if row['hp_error'] is not None: self.tower.append(row['hp_error'])
            return
        self.counts['unit_rows']+=1
        self.counts['matched' if row['missing'] is None else 'missing_'+row['missing']]+=1
        if row['position_error_tiles'] is not None: self.position.append(row['position_error_tiles'])
        if row['hp_error'] is not None: self.hp.append(row['hp_error'])

    def report(self):
        return dict(self.counts, position_mae=mean(self.position), hp_mae=mean(self.hp),
                    tower_hp_mae=mean(self.tower), tower_rows=len(self.tower))


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n', encoding='utf8')


def analyze(results, out):
    catalog,_=ps.load_catalog()
    summary=json.loads((results/'summary.json').read_text())
    top=summary['runtimes']['new']['ranking'][:8]
    groups=[r['group'].removesuffix(' movement/combat') for r in top]
    ages=defaultdict(Aggregate); times=defaultdict(Aggregate); total=Aggregate()
    group_ages=defaultdict(Aggregate); births=defaultdict(Counter)
    traces=defaultdict(list); plans=[]; changes=Counter(); reasons=Counter(); change_groups=defaultdict(Counter)
    hashes={}; n_samples=0; unmatched_no_age=0; censored=0; unavailable=0
    for path in sorted((results/'sources').glob('*.json')):
        source=json.loads(path.read_text()); match=source['match']
        new_path=results/'new'/(match+'.json'); fork_path=results/'fork'/(match+'.json')
        report=json.loads(new_path.read_text()); fork=json.loads(fork_path.read_text())
        assert report['source_sha256']==source['sha256']==fork['source_sha256']
        assert report['samples']==fork['samples'], 'new/fork trace mismatch'
        hashes[match]={label:hashlib.sha256(p.read_bytes()).hexdigest()
                       for label,p in [('source',path),('new',new_path),('fork',fork_path)]}
        old_plan=plan(source,True); fixed=plan(source,True,True)
        assert not fixed['blocks'], fixed['blocks']
        assert fixed['counts']['plays_used']+sum(s['kind']=='play' for s in fixed['skips'])==len(source['plays'])
        assert [a for a in old_plan['actions'] if a['side']==source['observer_side']]==[
            a for a in fixed['actions'] if a['side']==source['observer_side']]
        assert fixed['actions']==sorted(fixed['actions'],key=lambda a:(a['tick'],a['row']))
        plans.append(dict(match=match, source_sha256=source['sha256'], counts=fixed['counts'],
                          actions=fixed['actions'], receipts=fixed['inference_receipts'], skips=fixed['skips']))
        changes['matches']+=1; changes['original_opponent_injections']+=old_plan['counts']['opponent_injections']
        changes['retained_opponent_injections']+=fixed['counts']['opponent_injections']
        changes['own_plays_unchanged']+=fixed['counts']['own_plays']
        changed_match=False
        for receipt in fixed['inference_receipts']:
            name=receipt['name']; reasons[receipt['reason']]+=1; change_groups[name]['original']+=1
            if receipt['status']=='excluded':
                changes['excluded']+=1; change_groups[name]['excluded']+=1; changed_match=True
            else:
                change_groups[name]['retained']+=1
                a,b=receipt['original'],receipt['replacement']
                changes['form_pinned']+=1
                changes['nonbase_form_pinned']+=receipt['observed_form']!=0
                changes['timing_changed']+=a['tick']!=b['tick']
                changes['position_changed']+=(a['x'],a['y'])!=(b['x'],b['y'])
                if a!=b:
                    changes['retained_tick_or_position_changed']+=1; change_groups[name]['retimed_or_retargeted']+=1
                    changed_match=True
        changes['matches_with_changes']+=changed_match
        tracker=Tracks(role_limits(source,catalog) if report.get('artefact_fixes') else None)
        live={}; first={}
        for frame in source['frames']:
            assigned=tracker.assign(frame['tick'],frame['bodies']);live[frame['tick']]=assigned
            for key,b in assigned.items():
                if not b['tower']: first.setdefault(key,frame['tick'])
        histories=defaultdict(list)
        for si,sample in enumerate(report['samples']):
            if sample.get('unavailable'):
                unavailable+=1;continue
            if not sample['rows']:continue
            n_samples+=1
            for ri,row in enumerate(sample['rows']):
                total.add(row);times[time_bin(sample['tick'])].add(row)
                if row['tower']:continue
                name=catalog.get(row['card_id'],{}).get('display_name',str(row['card_id']))
                key=row['identity']; born=first.get(key)
                b=live.get(sample['tick'],{}).get(key)
                # Age is defined only for a currently observed LIVE body, not a
                # simulator-only ordinal which could match a future live unit.
                if b is None or born is None or sample['tick']<born:
                    unmatched_no_age+=1;continue
                age=sample['tick']-born
                if born==source['frames'][0]['tick']:censored+=1
                ages[age_bin(age)].add(row);group_ages[name,age_bin(age)].add(row)
                if name in groups:
                    histories[key].append(dict(sample_index=si,row_index=ri,tick=sample['tick'],
                        age_ticks=age,identity=key,live={k:b[k] for k in ('x','y','hp','max_hp','card_id')},
                        position_error_tiles=row['position_error_tiles'],hp_error=row['hp_error'],
                        missing=row['missing'],mismatch=row['mismatch']))
        for key,history in histories.items():
            name=catalog.get(history[0]['live']['card_id'],{}).get('display_name',str(history[0]['live']['card_id']))
            birth=history[0];bad=next((h for h in history if h['mismatch']),None)
            births[name]['tracks']+=1
            births[name]['first_row_mismatch' if birth['mismatch'] else 'first_row_aligned']+=1
            if bad and not birth['mismatch']:births[name]['later_divergence']+=1
            births[name]['first_row_missing']+=birth['missing'] is not None
            # Four first representative tracks per ranked group, plus all hut
            # bodies, enough to show root/child identity and growth, not cherry-pick.
            if len(traces[name])<4:
                traces[name].append(dict(match=match, identity=key, first_seen_tick=first[key],
                    first_mismatch_tick=bad['tick'] if bad else None,
                    first_mismatch_age_ticks=bad['age_ticks'] if bad else None,
                    report=f'new/{match}.json', source=f'sources/{match}.json',
                    rows=history[:12], nearby_commands=[c for c in report['commands'] if
                      c['name']==name and abs(c['tick']-birth['tick'])<=100]))
    changes['excluded_or_retimed_or_retargeted']=changes['excluded']+changes['retained_tick_or_position_changed']
    assert changes['original_opponent_injections']==changes['retained_opponent_injections']+changes['excluded']
    for row in top:
        row['first_observation']=dict(births[row['group'].removesuffix(' movement/combat')])
    overall=total.report();original=summary['runtimes']['new']
    assert n_samples==original['ticks']
    assert abs(overall['position_mae']-original['unit_position_mae_tiles'])<1e-10
    assert abs(overall['hp_mae']-original['unit_hp_mae'])<1e-10
    assert abs(overall['tower_hp_mae']-original['tower_hp_mae'])<1e-10
    assert sum(a.counts['unit_rows'] for a in ages.values())+unmatched_no_age==total.counts['unit_rows']
    output=dict(status='OFFLINE_BASELINE_TRIAGE_AND_REPLAN_NO_SIM', results=str(results),
                catalog_sha256=hashlib.sha256(ps.CATALOG.read_bytes()).hexdigest(),
                body_count_table_sha256=hashlib.sha256(ps.STATS.read_bytes()).hexdigest(),
                matches=len(plans), decision_rows=n_samples, unavailable_decisions=unavailable,
                new_fork_samples_identical=True, confirmed_mechanic_errors=[],
                overall=overall, changes=dict(changes), exclusion_and_inference_reasons=dict(reasons),
                changes_by_group={k:dict(v) for k,v in sorted(change_groups.items())},
                age_basis='since first observed live body; actual spawn unavailable; left-censored',
                age_boundaries_ticks=[0,40,100,200], age_without_live_body_rows=unmatched_no_age,
                opening_left_censored_rows=censored,
                age_mae={k:ages[k].report() for k in AGE_BINS},
                match_time_mae={k:times[k].report() for k in TIME_BINS}, top8=top,
                group_age_mae={g:{k:group_ages[g,k].report() for k in AGE_BINS} for g in groups})
    out.mkdir(parents=True,exist_ok=True)
    dump(out/'analysis.json',output);dump(out/'plans.json',plans);dump(out/'traces.json',dict(traces))
    dump(out/'input_hashes.json',hashes)
    return output


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=DEFAULT_RESULTS)
    ap.add_argument('--out',type=Path,default=HERE/'triage')
    ap.add_argument('--verify',action='store_true',help='recompute in memory/files and enforce source/metric/accounting assertions')
    a=ap.parse_args(); result=analyze(a.results,a.out)
    assert not any(m in sys.modules for m in ('royalesim','royalegym','pipeline.royale_runtime'))
    print(json.dumps({k:result[k] for k in ('matches','decision_rows','changes','age_mae','match_time_mae')},indent=2))
    print('PARITY_TRIAGE_VERIFIED')


if __name__=='__main__':main()
