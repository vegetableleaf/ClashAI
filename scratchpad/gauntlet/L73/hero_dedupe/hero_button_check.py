"""L73 hero dedupe: the live ability button (L68/live_reader/hero_button.should_press) picks its hero as the FIRST
own-side entity whose card_id is in hero_card_ids | {203000023} after dedupe_hero_bodies (hero_button.py:127-132).
Check that object is a named IceWizardHero on every named group, in both list orders, by spying on the hero argument
should_press passes to ice_wizard_should_press. Old (fd3aad4) vs new dedupe. Writes hero_button_check.json."""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[3]
sys.path[:0] = [str(WT), str(WT / 'scratchpad/gauntlet/L68/live_reader')]
import hero_button  # noqa: E402
import pipeline.reader_identity_aliases as ria  # noqa: E402
from measure import old_fn  # noqa: E402

ICE_WIZARD = 26000023


def main():
    seen = []
    hero_button.ice_wizard_should_press = lambda f, side, hero, names=None: (seen.append(hero), (False, 'spy'))[1]
    new, old = ria.dedupe_hero_bodies, old_fn()
    c = Counter()
    for line in open(HERE / 'named_groups.jsonl'):
        g = json.loads(line)
        if not any(e.get('native_name') == 'IceWizardHero' for e in g['objs']):
            continue
        for oname, objs in (('as_listed', g['objs']), ('reversed', g['objs'][::-1])):
            for fname, fn in (('old', old), ('new', new)):
                ria.dedupe_hero_bodies = fn            # should_press imports it from the module at call time
                seen.clear()
                hero_button.should_press({'entities': [dict(e) for e in objs]}, g['side'], {ICE_WIZARD})
                picked = seen[0]
                c[f'{fname} {oname} picked {picked.get("native_name") if picked else None}'] += 1
    ria.dedupe_hero_bodies = new
    out = dict(sorted(c.items()))
    (HERE / 'hero_button_check.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
