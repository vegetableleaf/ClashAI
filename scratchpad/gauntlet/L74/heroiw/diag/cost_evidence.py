"""Reproduce the ability/deploy cost finding from local device tables, no SIM."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DEVICE = ROOT/'scratchpad/gauntlet/L74/apktables/out/device_builds/20261012T221627332682Z-50188'
PIN = 'cacb7005f0e441797c533e91ab4f44820f9919d4'


def evidence():
    extraction = json.loads((DEVICE/'extraction.json').read_text())
    names = ['csv_logic/characters/hero_form/ice_wizard_hero.toml', 'csv_logic/spells_hero_form.csv']
    files = {}
    for name in names:
        path = DEVICE/'tables'/name
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        source = extraction['files'][name]
        assert sha == source['sha256']
        files[name] = dict(path=path.relative_to(ROOT).as_posix(), sha256=sha, source=source['source'])
    toml = tomllib.loads((DEVICE/'tables'/names[0]).read_text(encoding='utf8'))
    ability = toml['ABILITY']['IceWizardHero_ability']
    assert toml['EXT']['IceWizardHero']['Ability'] == 'IceWizardHero_ability'
    with (DEVICE/'tables'/names[1]).open(encoding='utf8', newline='') as stream:
        spell = next(r for r in csv.DictReader(stream) if r['Name'] == 'IceWizard_hero')
    selected = subprocess.check_output(['git', '-C', str(ROOT/'research/ext/Royale/RoyaleSim'), 'show',
                                        f'{PIN}:data/derived/cards-160402017-20261006.json'])
    selected_iw = next(c for c in json.loads(selected)['hero_forms'] if c['form_of'] == 'IceWizard')
    tree = ast.parse((ROOT/'pipeline/own_ability.py').read_text())
    supplement = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'SUPPLEMENT' for t in n.targets))
    # Evaluate only the literal dict constructor in this reviewed static assignment.
    live = eval(compile(ast.Expression(supplement.value), '<supplement>', 'eval'), {'__builtins__': {}, 'dict': dict})
    return dict(ability_cost=ability['ManaCost'], deploy_cost=int(spell['ManaCost']),
                ability_row={k: ability[k] for k in ('ManaCost', 'MaxCharges', 'RefundWindow', 'OnActivationAction')},
                ability_row_name='ABILITY.IceWizardHero_ability',
                deploy_row={k: spell[k] for k in ('Name', 'ManaCost', 'SummonCharacter')},
                files=files, extraction_fingerprint=extraction['fingerprint'],
                selected_sim_source=dict(pin=PIN, table='data/derived/cards-160402017-20261006.json',
                                         sha256=hashlib.sha256(selected).hexdigest(),
                                         ability_cost=selected_iw['ability']['mana_cost'], deploy_cost=selected_iw['elixir']),
                live_supplement_cost=live['ice-wizard', 2]['mana_cost'],
                conclusion='Device 2; SIM selected source 2; HEROIW prior smoke charged 2. No table/adapter cost mismatch. Supplement 1 conflicts; left unchanged. Pod records actual wheel table and zero-tick debit per attempt.')


if __name__ == '__main__':
    result = evidence()
    (HERE/'device_cost.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, indent=2))
