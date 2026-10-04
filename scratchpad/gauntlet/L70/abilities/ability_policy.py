"""Plain JSON + NumPy inference, no sklearn or engine dependency.

predict(ability, features) returns P(press within the next 1.0s), conditional on
being alive and available. Caller enforces lifetime, charges and cooldown.
Features may be a name->number mapping or an (..., 14) array in FEATURE_NAMES order.
version='v1' (default, unchanged) loads ability_models.json; version='v2' loads the
timing-calibrated ability_models_v2.json (same interface; seconds_since_deploy gets a
piecewise-linear timing term and the intercept is calibrated to native pressed share).
charge=1 (v2 only, boss-bandit's second charge) adds the model's second_charge_offset.
This is a horizon probability, not a per-engine-tick probability. For a decision
interval dt seconds, use 1-(1-p)**dt as an approximate cadence correction.
"""
import json
from pathlib import Path
import numpy as np

_BUNDLES = {}
FILES = {'v1': 'ability_models.json', 'v2': 'ability_models_v2.json'}
FEATURE_NAMES = ['seconds_since_deploy', 'hp_fraction', 'nearest_enemy_unit_tiles',
                 'nearest_enemy_building_or_tower_tiles', 'enemy_count_3', 'enemy_hp_3',
                 'enemy_count_5', 'enemy_hp_5', 'in_enemy_half', 'nearest_enemy_crown_tower_tiles',
                 'owner_elixir', 'match_phase', 'elixir_multiplier', 'crowns_diff']

def sigmoid(z):
    z=np.clip(z,-40,40)
    return 1/(1+np.exp(-z))

def tree_values(nodes,x):
    out=np.empty(len(x),float)
    def walk(i,idx):
        node=nodes[i]
        if 'value' in node:out[idx]=node['value'];return
        m=x[idx,node['feature']]<=node['threshold']
        walk(node['left'],idx[m]);walk(node['right'],idx[~m])
    walk(0,np.arange(len(x)))
    return out

def predict_model(model,x,charge=0):
    x=np.asarray(x,dtype=float); scalar=x.ndim==1
    x=np.atleast_2d(x)
    if x.shape[-1]!=len(FEATURE_NAMES) or not np.isfinite(x).all():
        raise ValueError('Expected finite values in the 14 documented feature columns')
    if model['type']=='phase1_timing':
        # Empirical discrete first-press hazard, conditioned on inferred phase-1 exposure.
        age=np.clip(np.floor(x[:,0]).astype(int),0,len(model['hazard'][0])-1)
        ph=np.clip(x[:,11].astype(int),0,3)
        p=np.asarray(model['hazard'])[ph,age]
    elif model['type'] in ('logistic_timing','gbt_timing'):
        score=np.full(len(x),model['intercept']+(model.get('second_charge_offset',0.) if charge else 0.),float)
        if model['type']=='logistic_timing':
            score+=((x-np.asarray(model['mean']))/np.asarray(model['scale']))@np.asarray(model['coefficients'])
        else:
            z=(x-np.asarray(model['mean']))/np.asarray(model['scale'])
            score+=model['trees_scale']*sum(model['learning_rate']*tree_values(t,z) for t in model['trees'])
        score+=np.interp(x[:,0],model['timing']['knots'],model['timing']['values'])
        p=sigmoid(score)
    else:
        z=(x-np.asarray(model['mean']))/np.asarray(model['scale'])
        score=np.full(len(z),model['intercept'],float)
        if model['type']=='logistic':score+=z@np.asarray(model['coefficients'])
        elif model['type']=='gradient_boosted_trees':
            for tree in model['trees']:score+=model['learning_rate']*tree_values(tree,z)
        else:raise ValueError('Unknown model type')
        p=sigmoid(score)
    return float(p[0]) if scalar else p

def load(version='v1'):
    if version not in FILES:raise ValueError('version must be v1 or v2')
    if version not in _BUNDLES:
        _BUNDLES[version]=json.loads(Path(__file__).with_name(FILES[version]).read_text(encoding='utf8'))
    return _BUNDLES[version]

def predict(ability,features,version='v1',charge=0):
    model=load(version)['models'][ability]
    if isinstance(features,dict):features=[features[n] for n in FEATURE_NAMES]
    return predict_model(model,features,charge)
