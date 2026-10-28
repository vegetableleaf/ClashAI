"""Read-only public live evidence. No opponent player block is serialized."""
from dataclasses import asdict

from .live_mem import my_side_of
from .projectile_observation import objects, tokens_from_objects


def snapshot(frame, batch, info, pilot):
    side=my_side_of(frame)
    me=next(p for p in frame['players'] if int(p['side'])==side)
    if getattr(pilot,'barrel_decoy',False):   # GB-DECOY: the objects the model saw
        from .barrel_decoy import objects as decoy_objects
        decoded=decoy_objects(frame,source='reader')
    else:
        decoded=objects(frame,source='reader')
    normalized=tokens_from_objects(decoded,side,pilot.gid)
    def active(values):
        return values[values[:,0]>0].tolist()
    def tensor(name):
        return batch[name][0].detach().cpu().numpy()
    fields=('side','x','y','card_id','hp','max_hp','kind','address','category')
    shots=('side','x','y','card_id','target_x','target_y','time_to_impact_ms')
    return dict(schema=1,source='public_reader_and_actual_model_batch',
        feature_version=pilot.feature_version,observer_side=side,
        raw_tick=int(frame['game_tick']),model_tick=round(info['bs'].t_sec/.05),
        own_elixir_raw=me['elixir_raw']/1e4,model_own_elixir=info['bs'].my_elixir,
        opponent_elixir_estimate=info['bs'].opp_elixir,
        own_hand=[dict(card=int(c),form=int(f),name=info['names'][di] if di>=0 else None,
                       deck_index=di,cost=float(cost))
                  for (c,f),di,cost in zip(info['hand'],info['hand_deck_indices'],info['costs'])],
        raw_bodies=[{k:e[k] for k in fields if k in e} for e in frame.get('entities',[])],
        raw_projectiles=[{k:e[k] for k in shots if k in e} for e in frame.get('projectiles',[])],
        normalized_current_projectiles=active(normalized['projectiles']),
        model_projectiles=active(tensor('projectiles')) if 'projectiles' in batch else [],
        model_effects=active(tensor('effects')) if 'effects' in batch else [],
        model_bodies=[asdict(u) for u in info['bs'].units],
        model_towers=[asdict(t) for t in info['bs'].towers],
        coordinate_contract='raw millitiles; normalized/model own frame x/18 tiles y/32 tiles; own edge y=1',
        public_lookahead_counts=info.get('public_lookahead_counts',{}))
