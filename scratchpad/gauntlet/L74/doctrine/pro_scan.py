"""One row per player-side of every 1v1 HF pro replay (L67/hf/replays): deck, X-Bow flags, result, crowns, replay length,
final tower HP, tower level -> pro_scan.parquet. Exact inputs for the crown-state tables (X-Bow sides + non-X-Bow baseline).
    icebow/.venv/Scripts/python.exe -I pro_scan.py   (idle priority)"""
import glob
import sys
import time
from pathlib import Path

import polars as pl

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ICEBOW8 = sorted({"tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons"})
J = pl.col('battle').str.json_path_match


def side(s, o):
    p = f'$.{s}.players[0]'
    base = pl.col(f'{s}_deck_raw').str.extract_all(r'"card_key":"[^"]+"').list.eval(
        pl.element().str.slice(12).str.strip_chars('"').str.replace(r'-(ev1|ev2|hero)$', ''))
    return [base.alias('deck'), J(f'{p}.tower_card.level').cast(pl.Int16).alias('tower_lv'),
            J(f'$.{s}.crowns').cast(pl.Int16).alias('crowns'), J(f'$.{o}.crowns').cast(pl.Int16).alias('opp_crowns'),
            *[J(f'{p}.final_tower_hitpoints.{k}').cast(pl.Int32).alias(f'own_{k}') for k in ('king', 'princess_left', 'princess_right')],
            *[J(f'$.{o}.players[0].final_tower_hitpoints.{k}').cast(pl.Int32).alias(f'opp_{k}')
              for k in ('king', 'princess_left', 'princess_right')],
            pl.when(pl.col('result') == 'draw').then(0.5).when((pl.col('result') == 'victory') == (s == 'team')).then(1.0)
            .otherwise(0.0).alias('win'), pl.lit(s).alias('side')]


out = []
t0 = time.time()
for f in sorted(glob.glob(str(REPO / 'scratchpad/gauntlet/L67/hf/replays/part-*.parquet'))):
    df = pl.read_parquet(f, columns=['replay_tag', 'battle_type', 'game_mode', 'result', 'payload_json'])
    df = df.with_columns(pl.col('payload_json').str.json_path_match('$.battle').alias('battle'),
                         pl.col('payload_json').str.json_path_match('$.replay.duration.timeline_seconds').cast(pl.Float64)
                         .alias('dur')).drop('payload_json')
    df = df.with_columns(J('$.team.players[0].deck').alias('team_deck_raw'), J('$.opponent.players[0].deck').alias('opponent_deck_raw'),
                         J('$.team.players[1].deck').alias('team_p2'))
    df = df.filter(pl.col('team_p2').is_null())
    for s, o in (('team', 'opponent'), ('opponent', 'team')):
        out.append(df.select('replay_tag', 'battle_type', 'game_mode', 'dur', *side(s, o),
                             pl.col(f'{o}_deck_raw').str.contains('"card_key":"x-bow', literal=True).alias('opp_xbow')))
    print(Path(f).name, round(time.time() - t0), 's', flush=True)
d = pl.concat(out).with_columns(pl.col('deck').list.contains('x-bow').alias('xbow'),
                                (pl.col('deck').list.sort() == pl.lit(ICEBOW8)).alias('icebow8'))
d.write_parquet(HERE / 'pro_scan.parquet')
print(d.shape, d['xbow'].sum(), d['icebow8'].sum())
