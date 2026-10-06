"""Read-only provenance, schema, and artifact helpers for forecast readiness."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;LOOP=HERE.parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT))
SEQ=ROOT/'icebow/data/bench/hand_retention_sequence_20261006'
OLD=LOOP/'hand_retention_integration/sequence_data'
RAW=ROOT/'icebow/data/bench/match_adaptation_20261005/rows.npz'
BINDING=LOOP/'match_adaptation/prepared.json'
OUT=ROOT/'icebow/data/bench/opponent_forecast_readiness_20261006'
COLS=['status','forecast_class','command_index','command_tick','command_card','command_count',
 'public_index','public_tick','public_card','public_count','join_count','join_index','delay',
 'window_complete','end_tick','sighting_gap','sighting_unknown']
STATUS=['eligible','no_command_full_horizon','no_command_right_censored','ambiguous_next_command',
 'unknown_command','Mirror_command','no_sighting_full_delay_window','ambiguous_next_sighting',
 'untrusted_or_unknown_sighting','pending_prior_sighting','wrong_first_sighting_card',
 'delay_out_of_bounds','nonunique_or_wrong_command_join','no_command_but_sighting_within400',
 'sighting_window_censored']
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def arrays(p):
 with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def bindings():
 files=[*HERE.glob('*.py'),HERE/'PLAN.md',HERE/'METRICS.md',RAW,BINDING,
  *[OLD/n for n in ('shared.py','collect.py','verify.py','started.json','collected.json','verified.json','reviewed.json')],
  SEQ/'public_events.jsonl',SEQ/'features.npz',ROOT/'pipeline/dataset_gen.py',ROOT/'pipeline/vocab.py']
 return {str(p.relative_to(ROOT)):sha(p) for p in files}
def load_training():
 old=read(OLD/'collected.json');assert old['complete'] and read(OLD/'verified.json')['complete'] and read(OLD/'reviewed.json')['complete']
 for n in ('public_events.jsonl','features.npz'):assert sha(SEQ/n)==old['outputs'][n]
 b=read(BINDING);assert sha(RAW)==b['rows_sha256']
 r=arrays(RAW);f=arrays(SEQ/'features.npz');assert np.array_equal(r['ids'],f['ids'])
 m=r['part']==0;assert int(m.sum())==213995 and len(np.unique(r['rep'][m]))==1573
 assert not set(r['rep'][m])&set(r['rep'][~m])
 rows={k:v[m] for k,v in r.items()};features={k:v[m] for k,v in f.items()}
 return b,rows,features
def streams(trainreps):
 seen=set()
 with (SEQ/'public_events.jsonl').open(encoding='utf-8') as f:
  for line in f:
   x=json.loads(line)
   if x['rep'] not in trainreps:continue
   assert x['rep'] not in seen;seen.add(x['rep']);yield x
 assert seen==trainreps
def label_hashes(rows):
 return {k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in rows.items() if k.startswith('y_')}
