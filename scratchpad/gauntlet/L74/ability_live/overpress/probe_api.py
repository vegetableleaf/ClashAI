"""List the SIM BattleState entity / spell / player fields after a reset (fork36 runtime, Hero IW deck)."""
from pipeline.royale_runtime import activate
activate()
from pipeline.royale_env import RoyaleSelfPlayEnv
ICE = ['Knight@evolution', 'Tesla@evolution', 'IceWizard@hero', 'Xbow', 'Rocket', 'Log', 'Tornado', 'Skeletons']
OPP = ['MegaKnight', 'Knight', 'Golem', 'HogRider', 'Musketeer', 'Fireball', 'Zap', 'Valkyrie']
env = RoyaleSelfPlayEnv(forms_mode='deck', hero_abilities=True, ability_policy='v2', feature_version=4)
env.reset(ICE, OPP, seed=1)
st = env.core.state()
print('state fields', [a for a in dir(st) if not a.startswith('_')])
print('entity fields', [a for a in dir(st.entities[0]) if not a.startswith('_')])
print('player fields', [a for a in dir(st.players[0]) if not a.startswith('_')])
print('abilities row', st.players[0].abilities)
print('battle methods', [a for a in dir(env.core._battle) if not a.startswith('_')])
print('unit_types sample', [u for u in env.core.unit_types() if 'Ice' in u])
print('hand', [env.names[c] for c in st.players[0].hand], st.players[0].elixir_milli)
