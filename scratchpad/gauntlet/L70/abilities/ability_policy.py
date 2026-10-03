"""Plain JSON + NumPy inference, no sklearn or engine dependency.

predict(ability, features) returns P(press within the next 1.0s), conditional on
being alive and available. Caller enforces lifetime, charges and cooldown.
Features may be a name->number mapping or an (..., 14) array in FEATURE_NAMES order.
This is a horizon probability, not a per-engine-tick probability. For a decision
interval dt seconds, use 1-(1-p)**dt as an approximate cadence correction.
"""
import json
from pathlib import Path
import numpy as np

_BUNDLE = None
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

def predict_model(model,x):
    x=np.asarray(x,dtype=float); scalar=x.ndim==1
    x=np.atleast_2d(x)
    if x.shape[-1]!=len(FEATURE_NAMES) or not np.isfinite(x).all():
        raise ValueError('Expected finite values in the 14 documented feature columns')
    if model['type']=='phase1_timing':
        # Empirical discrete first-press hazard, conditioned on inferred phase-1 exposure.
        age=np.clip(np.floor(x[:,0]).astype(int),0,len(model['hazard'][0])-1)
        ph=np.clip(x[:,11].astype(int),0,3)
        p=np.asarray(model['hazard'])[ph,age]
    else:
        z=(x-np.asarray(model['mean']))/np.asarray(model['scale'])
        score=np.full(len(z),model['intercept'],float)
        if model['type']=='logistic':score+=z@np.asarray(model['coefficients'])
        elif model['type']=='gradient_boosted_trees':
            for tree in model['trees']:score+=model['learning_rate']*tree_values(tree,z)
        else:raise ValueError('Unknown model type')
        p=sigmoid(score)
    return float(p[0]) if scalar else p

def predict(ability,features):
    global _BUNDLE
    if _BUNDLE is None:
        _BUNDLE=json.loads(Path(__file__).with_name('ability_models.json').read_text(encoding='utf8'))
    if isinstance(features,dict):features=[features[n] for n in FEATURE_NAMES]
    return predict_model(_BUNDLE['models'][ability],features)
