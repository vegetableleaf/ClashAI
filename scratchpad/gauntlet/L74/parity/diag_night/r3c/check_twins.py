"""Self-check of H-TWINS card_agree (004922@1682 numbers): swapped siblings agree; a changed fate still disagrees."""
import importlib.util, sys
sys.path.insert(0, r'C:/Users/benpe/ClashBot')
spec = importlib.util.spec_from_file_location('ft', r'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/parity/diag_night/r3c/fights_twins.py')
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
tw = {'b5': 0, 'd5': 0, 'fd': 0, 'a9': 0}
L = dict(spell=True, hit=['03', 'b5', 'd5'], enemy={'03': None, 'b5': 1728, 'd5': 1742, 'fd': None, 'a9': None}, tower=0, end=1922)
S = dict(spell=True, hit=['03', 'b5', 'fd'], enemy={'03': None, 'b5': 1742, 'd5': None, 'fd': 1728, 'a9': None}, tower=0, end=1922)
assert not F.card_agree(L, S)[0]                                     # no groups: identity scoring fails
assert F.card_agree(dict(L, twins=tw), dict(S, twins=tw))[:3] == (True, 0, 4)
S2 = dict(S, enemy=dict(S['enemy'], fd=1790))                         # a fate 62 ticks off: still a disagreement
assert F.card_agree(dict(L, twins=tw), dict(S2, twins=tw))[1] == 1
S3 = dict(S, hit=['03', 'b5'], enemy=dict(S['enemy'], fd=None))       # one sibling kill missing in the SIM
assert not F.card_agree(dict(L, twins=tw), dict(S3, twins=tw))[0]
print('ok')
