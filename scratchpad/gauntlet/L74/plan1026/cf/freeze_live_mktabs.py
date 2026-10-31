"""pod: perturbed copies of the 16.635.3 tables in /dev/shm (engine code untouched). Prints each variant's patched rows."""
import json, os, shutil
BASE = '/workspace/crforge_cache/tables/16.635.3'

def load(d, f):
    return json.load(open(os.path.join(d, f)))

def save(d, f, j):
    json.dump(j, open(os.path.join(d, f), 'w'), indent=1)

def patch(name, fn):
    d = '/dev/shm/fl_tabs_' + name
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(BASE, d)
    fn(d)
    print('made', d)

def freeze90(d):          # frozen units crawl at 10% instead of 0
    j = load(d, 'character_buffs.json'); c = j['rows']['IceWizardHero_FreezeBuff']['columns']
    assert c['SpeedMultiplier'] == -100 and c['HitSpeedMultiplier'] == -100
    c['SpeedMultiplier'] = -90; c['HitSpeedMultiplier'] = -90
    save(d, 'character_buffs.json', j)

def radius2000(d):        # freeze aura radius 2.5 t -> 2.0 t
    j = load(d, 'area_effect_objects.json'); c = j['rows']['IceWizardHero_FreezeAeo']['columns']
    assert c['Radius'] == 2500
    c['Radius'] = 2000
    save(d, 'area_effect_objects.json', j)

def cube4000(d):          # cube (= freeze) lifetime 5 s -> 4 s
    j = load(d, 'actions.json'); f = j['actions']['IceWizardHero_cube_lifetime_timer']['fields']
    assert f['Interval'] == 5000 and f['StartCounterAt'] == 5000
    f['Interval'] = 4000; f['StartCounterAt'] = 4000
    save(d, 'actions.json', j)
    j = load(d, 'characters.json'); c = j['rows']['IceWizardHero_IceCube']['columns']
    assert c['LifeTime'] == 5000
    c['LifeTime'] = 4000
    save(d, 'characters.json', j)

def slow15(d):            # the 30% slow after the freeze -> 15%
    j = load(d, 'character_buffs.json'); c = j['rows']['IceWizardHero_SlowBuff']['columns']
    assert c['SpeedMultiplier'] == -30
    c['SpeedMultiplier'] = -15; c['HitSpeedMultiplier'] = -15; c['SpawnSpeedMultiplier'] = -15
    save(d, 'character_buffs.json', j)

def noop(d):              # control: an untouched copy (the SME_TABLES path differs only)
    pass

for n, fn in (('cube4000', cube4000), ('slow15', slow15)):
    patch(n, fn)

def cube4000b(d):         # cube lifetime TIMER only 5 s -> 4 s (the character's LifeTime stays 5000)
    j = load(d, 'actions.json'); f = j['actions']['IceWizardHero_cube_lifetime_timer']['fields']
    f['Interval'] = 4000; f['StartCounterAt'] = 4000
    save(d, 'actions.json', j)

def slow0(d):             # no slow after the freeze
    j = load(d, 'character_buffs.json'); c = j['rows']['IceWizardHero_SlowBuff']['columns']
    c['SpeedMultiplier'] = 0; c['HitSpeedMultiplier'] = 0; c['SpawnSpeedMultiplier'] = 0
    save(d, 'character_buffs.json', j)

def radius3000(d):        # over-power control: radius 3.0 t
    j = load(d, 'area_effect_objects.json'); c = j['rows']['IceWizardHero_FreezeAeo']['columns']
    c['Radius'] = 3000
    save(d, 'area_effect_objects.json', j)

for n, fn in (('cube4000b', cube4000b), ('slow0', slow0), ('radius3000', radius3000)):
    patch(n, fn)
