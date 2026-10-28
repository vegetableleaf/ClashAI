"""Rule-level counterfactual on the recorded evo casts: the model's card and timing held fixed, the decoy token renamed
(barrel_decoy.objects). log_barrel then aims every in-flight Log at the real landing (one point: its covering cells are
all in that lane); barrel_lane moves a Knight / IceWizard / Skeletons / Tornado on my half into the real lane (one point
on my half, one lane). Tesla and plays on the enemy half are untouched. Exact for the lane only when a finite covering
cell exists (live masks illegal cells; logits are not logged), and NOT a model replay: with one barrel token the model
itself may pick another card, cell or time (untested)."""
import json, collections
ROLE = {'Log': 'log_barrel', 'Knight': 'barrel_lane', 'IceWizard': 'barrel_lane', 'Skeletons': 'barrel_lane',
        'Tornado': 'barrel_lane'}
meas = [o for o in json.load(open('results/measure_out.json')) if o['kind'] == 'evo']
c = collections.Counter()
for o in meas:
    name, lane, dt, dl, _ = o['first']
    before = lane == o['real']
    after = before or (name in ROLE and dl < 0)            # every evo first answer was in flight (dl < 0)
    c['casts'] += 1
    c['real_before'] += before
    c['real_after'] += after
    c[f'moved_by_{ROLE.get(name)}'] += after and not before
    c['still_wrong_' + name] += not after
print(dict(c))
