"""Step 4 training (DISTILL_PLAN.md): fine-tune the PLAIN checkpoint on the D3 teacher's (model input, final action) rows.

Rows are built in the imitation dataset's own format (pipeline.dataset_gen npz arrays) and trained with the imitation
trainer's own code: train_gen.GenRows batches, train_gen.losses (cell CE teacher-forced on the chosen card, card CE over
the 4 hand positions, gate BCE, 0.5 wait CE, 0.5 value CE, mirror p 0.5), eval_gen.evaluate. Only the target differs.

Row sampling = dataset.build_replay's, so the gate keeps the meaning the deploy threshold (tau .35) was set for:
  PLAY rows  every learner decision that played AND whose play the engine accepted at landing (imitation: accepted plays)
  WAIT rows  per --wait-stride tick bucket, the bucket's FIRST decision if it waited, no accepted play was decided in
             (t, t + --play-window], and an accepted play follows later (imitation drops rows after the last play)
  labels     card = the played deck slot's identity / hand position; cell = model_v3.cell_xy(cell) (cell_label inverts it);
             wait = the next accepted play's card; value = the game's crowns (for, against); split = crc32(census:seed)

    python scratchpad/gauntlet/L74/distill/train_distill.py --data GEN_DIR --init PLAIN.pt --out STUDENT.pt
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

INPUT_KEYS = ('sc', 'past', 'hand_card', 'hand_form', 'next_card', 'next_form', 'deck_card', 'deck_form',
              'opp_past', 'opp_cycle', 'projectiles', 'effects', 'own_ability')
IDENT16 = ('hand_card', 'hand_form', 'next_card', 'next_form', 'deck_card', 'deck_form')


def load_game(path):
    with np.load(path, allow_pickle=False) as z:          # closed: thousands of game files
        return {k: z[k] for k in z.files if k != 'meta'}, json.loads(str(z['meta']))


def select(g, wait_stride=40, play_window=20):
    """-> (play row ids, wait row ids, wait label decision id per wait row); see the module docstring."""
    tick, play, acc = g['tick'], g['play'].astype(bool), g['accepted'].astype(bool)
    plays = np.flatnonzero(play & acc)
    acc_ticks = tick[plays]
    first = np.r_[True, tick[1:] // wait_stride != tick[:-1] // wait_stride]
    waits, nxt = [], []
    for i in np.flatnonzero(first & ~play):
        j = np.searchsorted(acc_ticks, tick[i], side='right')
        if j == len(acc_ticks):
            continue                                            # after my last accepted play
        if acc_ticks[j] <= tick[i] + play_window:
            continue                                            # a play follows within the window
        waits.append(i)
        nxt.append(plays[j])
    return plays, np.asarray(waits, np.int64), np.asarray(nxt, np.int64)


def game_rows(g, meta, grid, wait_stride=40, play_window=20, val_pct=10):
    from pipeline.dataset import _tag_split
    from pipeline.model_v3 import cell_xy
    plays, waits, nxt = select(g, wait_stride, play_window)
    ids = np.r_[plays, waits].astype(np.int64)
    n, n_play = len(ids), len(plays)
    gate = np.r_[np.ones(n_play, np.int8), np.zeros(len(waits), np.int8)]
    hand_slot, slot_card = g['hand_slot'], g['slot_card']
    slot = g['slot'][plays]
    hit = hand_slot[plays] == slot[:, None]
    if not hit.any(1).all():
        raise ValueError(f"seed {meta['seed']}: a played slot is not in the hand")
    play_card = slot_card[plays, slot]
    mask = g['mask'][ids].astype(bool)
    m = mask.sum(1)
    if not (mask == (np.arange(mask.shape[1]) < m[:, None])).all():
        raise ValueError('unit mask is not a prefix')
    out = {k: g[k][ids] for k in INPUT_KEYS if k in g}
    out.update(
        tok=g['tok'][ids][mask], n_tok=m.astype(np.int64),
        y_gate=gate, y_hand_pos=np.r_[hit.argmax(1), -np.ones(len(waits))].astype(np.int8),
        y_card=np.r_[play_card, np.zeros(len(waits))].astype(np.int16),
        y_xy=np.r_[np.array([cell_xy(c, grid) for c in g['cell'][plays]]).reshape(-1, 2),
                   -np.ones((len(waits), 2))].astype(np.float32),
        y_wait_card=np.r_[play_card, slot_card[nxt, g['slot'][nxt]]].astype(np.int16),
        y_crowns=np.tile(np.array([meta['crowns_for'], meta['crowns_against']], np.int8), (n, 1)),
        tick=g['tick'][ids].astype(np.int32),
        split=np.full(n, _tag_split(f"{meta['census']}:{meta['seed']}", val_pct), np.int8))
    if 'unit_form' in g:
        out['unit_form'] = g['unit_form'][ids][mask]
    st = Counter(f'why:{w}' for w in g['why'][plays])           # which rule / head produced each play label
    st.update(decisions=len(g['tick']), play_rows=n_play, wait_rows=len(waits),
              refused_or_unlanded=int((g['play'].astype(bool) & ~g['accepted'].astype(bool)).sum()))
    return out, st


def build_rows(games, grid, wait_stride=40, play_window=20, val_pct=10):
    """[(arrays, meta)] -> (arrs in dataset_gen's npz layout, stats). Keeps only the selected rows of each game."""
    parts, st = {}, Counter()
    for g, meta in games:
        rows, s = game_rows(g, meta, grid, wait_stride, play_window, val_pct)
        st.update(s)
        st['games'] += 1
        for k, v in rows.items():
            parts.setdefault(k, []).append(v)
    arrs = {k: np.concatenate(v) for k, v in parts.items()}
    arrs['off'] = np.concatenate([[0], np.cumsum(arrs.pop('n_tok'))]).astype(np.int64)
    for k in IDENT16:
        arrs[k] = arrs[k].astype(np.int16)
    n = len(arrs['sc'])
    arrs.update(deck_id=np.zeros(n, np.int32), v3val=np.zeros(n, np.int8))
    return arrs, dict(st)


def main(argv=None):
    import torch
    from pipeline.eval_gen import evaluate
    from pipeline.model_gen import load_model
    from pipeline.train_gen import GenRows, losses
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True, help='gen_distill.py --out dir (searched for distill_*.npz)')
    ap.add_argument('--init', type=Path, required=True, help='the PLAIN student checkpoint (no refine heads)')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--epochs', type=int, default=2)
    ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--amp', choices=('none', 'bf16'), default='bf16')
    ap.add_argument('--no-mirror', action='store_true')
    ap.add_argument('--wait-stride', type=int, default=40)
    ap.add_argument('--play-window', type=int, default=20)
    ap.add_argument('--val-pct', type=int, default=10)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--max-steps', type=int, default=0, help='0 = all; >0 = smoke')
    a = ap.parse_args(argv)
    if a.out.resolve() == a.init.resolve():
        raise SystemExit('refusing to overwrite the init checkpoint')
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model, st = load_model(a.init, dev)
    if getattr(model, 'cell_refine', None) is not None or getattr(model, 'tower_refine', None) is not None:
        raise SystemExit('the student must be the plain checkpoint: no refine heads at decode')
    grid = str(st['args'].get('grid', 'lattice'))
    files = sorted(a.data.rglob('distill_*.npz'))
    if not files:
        raise SystemExit(f'no distill_*.npz under {a.data}')

    def games():
        for f in files:
            g, meta = load_game(f)
            if meta['card_vocab'] != st['card_vocab'] or meta['feature_version'] != model.feature_version:
                raise SystemExit(f'{f}: teacher rows do not match the student (card vocab / feature version)')
            yield g, meta
    arrs, stats = build_rows(games(), grid, a.wait_stride, a.play_window, a.val_pct)
    tr_idx, va_idx = np.flatnonzero(arrs['split'] == 0), np.flatnonzero(arrs['split'] == 1)
    rows = GenRows(arrs, tr_idx, dev)
    va = rows.view(va_idx)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    steps = a.epochs * (len(tr_idx) // a.bs)
    if a.max_steps:
        steps = min(steps, a.max_steps)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(steps, 1), pct_start=0.05)
    amp = a.amp == 'bf16' and dev.type == 'cuda'
    log = a.out.with_suffix('.log.jsonl')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    log.write_text('')

    def note(d):
        print(json.dumps(d), flush=True)
        with log.open('a') as f:
            f.write(json.dumps(d)+'\n')
    val = (lambda: evaluate(model, va, grid=grid)) if len(va_idx) else (lambda: {})    # tiny smoke: no val game
    val0 = val()
    note({'init': str(a.init), 'files': len(files), 'train_rows': len(tr_idx), 'val_rows': len(va_idx),
          'steps': steps, 'stats': stats, 'val0': val0})
    t0, step, hist = time.time(), 0, []
    while step < steps:
        model.train()
        perm = rng.permutation(tr_idx)
        acc = Counter()
        for s in range(0, len(perm)-a.bs+1, a.bs):
            if step >= steps:
                break
            b = rows.batch(perm[s:s+a.bs])
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=amp):
                loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=grid)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); step += 1
            acc.update(parts); acc['n'] += 1
            if step % 200 == 0:
                note({'step': step, 'of': steps, 'loss_parts': {k: round(v/acc['n'], 4) for k, v in acc.items() if k != 'n'},
                      'min': round((time.time()-t0)/60, 1)})
        hist.append({'step': step, **val()})
        note({'val': hist[-1]})
    sd = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save({**st, 'model': sd, 'distill': {
        'init': str(a.init).replace('\\', '/'), 'args': {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
        'stats': stats, 'val0': val0, 'hist': hist}}, a.out)
    note({'saved': str(a.out), 'minutes': round((time.time()-t0)/60, 1)})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
