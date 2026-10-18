"""Render already verified pod statistics; no local simulator or heavy analysis."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path('C:/Users/benpe/pod_backup_weekend/codex1018')
rows=[]
latest={}
for p in sorted(ROOT.glob('*/*/codex1018_parity/paired_scores.json')):
    latest[p.parents[2].name]=p
for p in latest.values():
    receipt=p.parents[1]/'COPY_VERIFIED.json'
    assert json.loads(receipt.read_text())['verified']
    doc=json.loads(p.read_text())
    for row in doc['results']:rows.append(dict(row,backup=str(p)))
(HERE/'round7_paired_scores.json').write_text(json.dumps(rows,indent=2)+'\n')
lines=['# Round 7: paired readout against FIN12','',
       'SIM fight parity, not candidate win rate. CIs resample whole matches in pairs (2,000 draws, seed 0), using the existing strict-fight and card-agreement definitions. Completed affected-match files replace the matching FIN12 files, as in diag_night/r5c/cmp.py. Positive deltas are percentage points of raw agreement. These are correlated exploratory arms, without multiple-comparison correction. A statistical gain alone is not a verifier land verdict.','',
       '| Arm | Cohort | Raw agreement [95% CI] | Delta pp [paired 95% CI] | Up / down | Fights |',
       '|---|---|---|---|---|---|']
for row in rows:
 for cohort,s in row['cohorts'].items():
    lo,hi=s['arm_ci95'];dl,dh=s['delta_ci95_pp']
    lines.append(f"| {row['label']} | {cohort} | {s['arm_raw']:.4f} [{lo:.4f}, {hi:.4f}] | {s['delta_pp']:+.3f} [{dl:+.3f}, {dh:+.3f}] | {s['up']} / {s['down']} | {s['arm_n']} |")
lines+=['','H-FIXED-AIM v2 and H-VOLLEY address the same volley issue; do not add their gains. The two IW press-date approaches also overlap. The r7a joint was only run on the upgraded cohort; no full-cohort result is implied. The cube-v2 row uses the available finished shards and is not evidence of unseen shards. Fight eligibility and denominators can change between arms: for example, H-NEGHP has zero changed common-fight scores but a different fight count, so its raw-agreement delta is not a common-fight improvement. The paired intervals resample whole matches and retain those denominator changes.','',
        'Raw per-result tables below describe each result directory itself, which can be a subset or a shard. Compare populations before comparing their raw percentages. These are the original scorer CIs, not substituted for the paired full-cohort comparisons above.','',
        '| Pod / result directory | Cohort | Matches | Fights | Raw agreement [95% CI] |',
        '|---|---|---:|---:|---|']
seen=set();raw=[]
for receipt in sorted(ROOT.glob('*/*/COPY_VERIFIED.json'),reverse=True):
    d=json.loads(receipt.read_text())
    for p in receipt.parent.glob('results/*/ceiling_strict.json'):
        ident=(d['port'],p.parent.name)
        if ident in seen:continue
        seen.add(ident);j=json.loads(p.read_text());s=j.get('overall')
        if not s:continue
        raw.append(dict(port=d['port'],arm=p.parent.name,cohort=j.get('cohort'),overall=s))
        lo,hi=s['agree_ci']
        lines.append(f"| {d['port']} / {p.parent.name} | {j.get('cohort')} | {s['matches']} | {s['n']} | {s['agree']:.3f} [{lo:.3f}, {hi:.3f}] |")
(HERE/'ROUND7_RESULTS.md').write_text('\n'.join(lines)+'\n')
(HERE/'round7_raw_scores.json').write_text(json.dumps(raw,indent=2)+'\n')
print('PARITY_TABLES',len(rows),'paired arms;',len(raw),'raw result directories')
for r in rows:
 if r['label'] in ('H-SNAP-BACK','H-PREROLL','H-IW-PRESS-DATE v5','H-VOLLEY','H-VOLLEY + H-CUBE-DATE v2','verifier S-EK-HITTICK'):
    print(r['label'],r['cohorts'].get('upgraded'))
