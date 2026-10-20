"""Print the O2 fine-tune holdout curves (pod_backup_weekend/o2/out/hist_live_s*.json; 30-epoch run).  python o2_summary.py"""
import json
from pathlib import Path
for s in (0, 1):
    h = json.loads(Path(f'C:/Users/benpe/pod_backup_weekend/o2/out/hist_live_s{s}.json').read_text())
    print(f"seed {s}: train rows {h['train_rows']}, holdout rows {h['val_rows']}")
    print('  epoch  card_top1  cell_tile_top1  gate_bal_acc  cell_nll  wait_top1  place_dist_tiles')
    for e in h['hist']:
        if e['epoch'] in (0, 1, 2, 5, 10, 15, 16, 20, 25, 29, 30):
            print(f"  {e['epoch']:5d}  {e['card_top1']:.4f}     {e['cell_tile_top1']:.4f}          {e['gate_bal_acc']:.4f}        "
                  f"{e['cell_nll']:.3f}     {e['wait_top1']:.4f}     {e['place_dist']:.3f}")
