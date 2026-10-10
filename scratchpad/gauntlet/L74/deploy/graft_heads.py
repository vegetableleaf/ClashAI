"""Graft the live model's CellRefine + TowerRefine add-ons onto the E4 u20 defence checkpoint."""
import torch
B = r'C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/'
live = torch.load(B + 'rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt', map_location='cpu')
base = torch.load(B + 'rseries_r3c/rseries_r3c_u0030_barrel.pt', map_location='cpu')
e4 = torch.load(B + 'rdef_e4/rdef_e4_u0020.pt', map_location='cpu')
heads = {k: v for k, v in live['model'].items() if k.startswith(('cell_refine.', 'tower_refine.', 'projectile_target_'))}
trunk = [k for k in live['model'] if k not in heads]
assert set(trunk) | {k for k in heads if k.startswith('projectile_target_')} == set(e4['model']) == set(base['model']), 'key sets differ'
same = sum(torch.equal(live['model'][k], base['model'][k]) for k in trunk)
print(f'heads {len(heads)} tensors; live trunk == fast base trunk on {same}/{len(trunk)} tensors')
drift = sum((e4['model'][k].float() - base['model'][k].float()).abs().sum().item() for k in trunk if e4['model'][k].is_floating_point())
size = sum(base['model'][k].float().abs().sum().item() for k in trunk if base['model'][k].is_floating_point())
print(f'E4 trunk drift from the fast base: {100 * drift / size:.2f}% of total |weights|')
for k in ('gen', 'args', 'd_c', 'card_vocab', 'architecture'):
    if k in live and k not in ('args',) and live.get(k) != e4.get(k) and k != 'card_vocab':
        print('meta differs:', k)
assert live['card_vocab'] == e4['card_vocab'], 'card vocab differs'
e4['model'] = {**e4['model'], **heads}
e4['grafted_heads_from'] = 'rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt'
torch.save(e4, B + 'rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt')
print('saved')
