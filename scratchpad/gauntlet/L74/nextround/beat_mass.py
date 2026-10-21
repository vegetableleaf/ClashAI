"""W15 lever 3: how much opponent-deck draw mass the BEAT weighting moves, on the two pools tn_base_s74 draws from.

    research/ext/Royale/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/nextround/beat_mass.py [census json]

'contains' = the rl_royale rule (a deck holding any BEAT card); 'wincon' = W13's measurement rule (anatomy.wincon: the first
WINCON-priority card of the deck is in BEAT). Pool weights = rl_royale.deck_weights at tn_base's alpha 1 / floor 0.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / 'scratchpad/gauntlet/L74/clx_ranked')]
import yaml  # noqa: E402

W = yaml.safe_load((REPO / 'scratchpad/gauntlet/L74/stepd/cfg/tn_tank3x_s74.yaml').read_text())['league_deck_weights']
WINCON = ('x_bow', 'mortar', 'royal_giant', 'lava_hound', 'golem', 'electro_giant', 'goblin_giant', 'giant', 'elixir_golem',
          'mega_knight', 'pekka', 'hog_rider', 'royal_hogs', 'ram_rider', 'battle_ram', 'balloon', 'graveyard', 'goblin_drill',
          'miner', 'goblin_barrel', 'wall_breakers', 'three_musketeers', 'sparky', 'skeleton_barrel', 'goblin_machine',
          'rune_giant', 'boss_bandit', 'giant_skeleton', 'skeleton_king', 'goblinstein', 'bowler', 'executioner')  # anatomy.py
SIX = {'Giant', 'ElectroGiant', 'RoyalHogs', 'BattleRam', 'Pekka', 'Golem'}                     # CLX_RANKED.md L3
BEAT = {'giant', 'electro_giant', 'royal_hogs', 'battle_ram', 'pekka', 'golem', 'goblin_giant', 'lava_hound', 'royal_giant',
        'elixir_golem', 'rune_giant', 'giant_skeleton', 'three_musketeers', 'boss_bandit'}                   # report.py


def slug(s):
    for suf in ('-ev1', '-hero'):
        s = s.removesuffix(suf)
    return {'x-bow': 'x_bow', 'wall-breakers': 'wall_breakers', 'skeleton-barrel': 'skeleton_barrel'}.get(s, s.replace('-', '_'))


def main():
    pools = sys.argv[1:] or ['share/data_20261020/decks_rl.json', 'scratchpad/gauntlet/L74/mix/decks_live_train.json']
    names = {}
    for f in pools:
        d = json.loads((REPO / f).read_text(encoding='utf-8'))['decks']
        for x in d:
            for e, s in zip(x['engine'], x['slugs']):
                names.setdefault(e.split('@')[0], slug(s))
        p = np.array([x['sides'] for x in d], float)
        p /= p.sum()
        six = np.array([any(e.split('@')[0] in SIX for e in x['engine']) for x in d])
        print(f'{f}: L3 six-card subset {sorted(SIX)} mass {p[six].sum():.3f}')
        has = np.array([any(e.split('@')[0] in W for e in x['engine']) for x in d])
        wc = np.array([next((w for w in WINCON if w in {slug(s) for s in x['slugs']}), 'other') in BEAT for x in d])
        q = p * np.where(has, 3.0, 1.0)
        q /= q.sum()
        print(f'{f}: {len(d)} decks | contains-BEAT mass {p[has].sum():.3f} -> x3 {q[has].sum():.3f} | '
              f'wincon-BEAT mass {p[wc].sum():.3f} -> under x3-contains {q[wc].sum():.3f} | '
              f'contains but wincon not BEAT {p[has & ~wc].sum():.3f}, wincon BEAT but not contained {p[wc & ~has].sum():.3f}')
    print('weight keys -> W13 slug:', {k: names.get(k) for k in W})


if __name__ == '__main__':
    main()
