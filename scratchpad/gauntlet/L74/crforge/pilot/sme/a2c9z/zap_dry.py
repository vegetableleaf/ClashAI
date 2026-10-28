"""A2c-9Z dry run: mech_rules.zap_buffs on an inputs file's plays (no re-extraction); prints every add / re-point.
python -I zap_dry.py INPUTS.jsonl LOGDIR [match suffix ...]"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
os.environ['SME_ZAP_ADD'] = os.environ.get('SME_ZAP_ADD', '1'); os.environ['SME_ZAP_POINT'] = os.environ.get('SME_ZAP_POINT', '1')
import extract, mech_rules  # noqa: E402
life, stats = extract.table_shims(extract.TABLES)
inp, logdir, want = sys.argv[1], sys.argv[2], sys.argv[3:]
for line in open(inp):
    r = json.loads(line)
    if want and r['match'][-6:] not in want:
        continue
    sides = {int(s): v for s, v in r['sides'].items()}
    if not any('Zap' in v['deck'] for v in sides.values()):
        continue
    log = []
    mech_rules.zap_buffs(os.path.join(logdir, r['match'] + '.jsonl'), r['plays'], sides, stats, log)
    for x in log:
        print(r['match'][-6:], 'F' if r['flags'] else 'c', x)
