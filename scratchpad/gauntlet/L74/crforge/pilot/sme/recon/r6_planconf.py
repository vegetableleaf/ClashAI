"""RECON-6 (pod): form corroboration of final plans: forms.plan_cost of the BASE plan (the extractor's plays) vs the FINAL plan of a RECON run, per opponent card with a form rule.
  python3 recon/r6_planconf.py INPUTS.jsonl RUNDIR m1,m2,...      # RUNDIR/<match>/recon_plan.json
cost 0 on the final plan and > 0 on the base = every observed Hero / EV1 form of the card is explained only after RECON's edits: the edits are corroborated by the forms
(independent of the ablation, which stays the owner's counting rule; this is extra evidence for the records whose ablation cannot run)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault('SME_TABLES', '/workspace/crforge_cache/tables/16.635.3')
import recon, forms  # noqa: E402

inp, rundir, ms = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
tab = recon.Tab()
ru = forms.rules(tab)
for l in open(inp):
    rec = json.loads(l)
    if not any(rec['match'].endswith(m) for m in ms):
        continue
    me = rec['my_side']
    base = recon.base_plan(rec, None)
    fin = json.load(open(os.path.join(rundir, rec['match'], 'recon_plan.json')))
    for side in (0, 1):
        b, f = forms.plan_cost(rec, base, side, tab, ru), forms.plan_cost(rec, fin, side, tab, ru)
        print(rec['match'][-13:], 'side', side, 'own' if side == me else 'opp', 'base cost', b, 'final cost', f)
