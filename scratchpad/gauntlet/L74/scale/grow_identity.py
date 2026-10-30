"""GROW-10M identity test: a grown checkpoint (grow.py) == its base on recorded live decisions, CPU.

    PY=icebow/.venv/Scripts/python.exe; T=scratchpad/gauntlet/L74/scale/grow_identity.py
    $PY -B $T run  CKPT OUT.pt [--rows]   live replay (b0_identity's 4 recorded CLXIII matches, 1,718 decisions) through
                                          this tree's live path with CKPT on CPU; --rows also keeps every model input b
    $PY -B $T cmp  BASE.pt GROWN.pt       live-path compare (decision dicts / taps / RNG states, max |log-prob diff| per head;
                                          g: every one of the k copies against the base g)
    $PY -B $T model BASE_CKPT GROWN_CKPT ROWS.pt [fp32|fp64|64v32] [STRIDE]
                                          model level on the recorded inputs: raw logits AND log-probs of gate, card, wait,
                                          value, g and the cell head for EVERY real hand card of the row; argmax actions
    $PY -B $T sym  GROWN_CKPT ROWS.pt     one backward on 16 rows: do the k copies get DIFFERENT gradients (not stuck equal)?
    $PY -B $T lat  CKPT ROWS.pt [cpu|cuda] [threads]
                                          batch-1 decide-path latency (encode_gen + heads_gen + cell head of the 4 hand
                                          slots), 200 timed reps after 20 warm-up, on recorded rows
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'scratchpad/gauntlet/L74/plan1026/pilot/ops')]
TENSOR_KEYS = ('gate', 'card', 'wait', 'value', 'g')


def run(ckpt, out, rows=False):
    import torch
    from b0_identity import logp, pilot_for
    from pipeline.tests.test_decide_identity import LIVE_DIR, LOGS, canon, read_log
    torch.set_num_threads(1)
    rec, heads, inputs = [], [], []
    for name in LOGS:
        start, ev = read_log(LIVE_DIR / name)
        pilot = pilot_for(start, ROOT / ckpt, 'cpu')
        cur = {}
        fwd = pilot._policy_forward

        def wrapped(b, fwd=fwd, cur=cur):
            if rows:
                cur['b'] = {k: (v.detach().clone() if torch.is_tensor(v) else v) for k, v in b.items()}
            o, cell_head = fwd(b)
            cur['heads'] = {k: logp(k, v) for k, v in o.items() if torch.is_tensor(v)}

            def ch(card, form):
                c = cell_head(card, form)
                cur.setdefault('cell', []).append(logp('cell', c))
                cur.setdefault('cell_args', []).append((card.clone(), form.clone()))
                return c
            return o, ch
        pilot._policy_forward = wrapped
        pilot.reset_match()
        f = None
        for e in ev:
            if e[0] == 'frame':
                f = e[1]
                pilot.observe(f)
            elif e[0] == 'decision' and f is not None and f['game_tick'] == e[1]:
                cur.clear()
                d = pilot.decide(f)
                tap = [d['hand_pos'], canon(d['xy']), canon(d.get('follow_ups'))] if d.get('play') else None
                rec.append(dict(log=name, tick=e[1], tap=tap, d=canon(d), rng=canon(pilot.rng_decisions.bit_generator.state)))
                if rows:
                    inputs.append(cur.pop('b'))
                heads.append(dict(cur))
            elif e[0] == 'confirmed' and None not in e[2:]:
                pilot.record_play(e[2], e[3], e[4], e[1] * 0.05)
            elif e[0] == 'ability':
                pilot.record_ability(e[1], e[2])
        print(f'{name}: {sum(r["log"] == name for r in rec)} decisions', flush=True)
    torch.save({'ckpt': ckpt, 'device': 'cpu', 'rec': rec, 'heads': heads}, out)
    if rows:
        torch.save(inputs, Path(out).with_suffix('.rows.pt'))


def g_diff(gb, gg):
    """max |copy_c(g grown) - g base| over the k copies (block layout)."""
    d = gb.shape[-1]
    k = gg.shape[-1] // d
    return max(float((gg[..., c * d:(c + 1) * d] - gb).abs().max()) for c in range(k))


def strip_p(x):
    """A decision dict without its logged probability floats (p_play, also inside follow_ups): what was DONE."""
    if isinstance(x, dict):
        return {k: strip_p(v) for k, v in x.items() if k != 'p_play'}
    if isinstance(x, list):
        return [strip_p(v) for v in x]
    return x


def cmp(pa, pb):
    import torch
    a, b = (torch.load(p, weights_only=False) for p in (pa, pb))
    n = len(a['rec'])
    assert n == len(b['rec']), (n, len(b['rec']))
    same_d = sum(x['d'] == y['d'] for x, y in zip(a['rec'], b['rec']))
    same_tap = sum(x['tap'] == y['tap'] for x, y in zip(a['rec'], b['rec']))
    same_rng = sum(x['rng'] == y['rng'] for x, y in zip(a['rec'], b['rec']))
    same_act = sum(strip_p(x['d']) == strip_p(y['d']) for x, y in zip(a['rec'], b['rec']))   # every field but logged p_play
    diff, cells = {}, 0
    for ha, hb in zip(a['heads'], b['heads']):
        assert ha['heads'].keys() == hb['heads'].keys(), (ha['heads'].keys(), hb['heads'].keys())
        for k in ha['heads']:
            x, y = ha['heads'][k], hb['heads'][k]
            v = g_diff(x, y) if k == 'g' else float((x - y).nan_to_num(0.0).abs().max())
            diff[k] = max(diff.get(k, 0.0), v)
        assert len(ha.get('cell', [])) == len(hb.get('cell', []))
        for x, y in zip(ha.get('cell', []), hb.get('cell', [])):
            cells += 1
            diff['cell'] = max(diff.get('cell', 0.0), float((x - y).abs().max()))
    plays = sum(x['tap'] is not None for x in a['rec'])
    print(f'{a["ckpt"]} vs {b["ckpt"]} (cpu): {n} decisions ({plays} plays), cell-head calls {cells}; decision dicts '
          f'{same_d}/{n}, ACTIONS (dicts minus the logged p_play floats) {same_act}/{n}, taps {same_tap}/{n}, RNG states '
          f'{same_rng}/{n}; max |diff| (log-probs; value / g raw) '
          + ', '.join(f'{k} {v:.3g}' for k, v in sorted(diff.items())))
    return same_act == same_rng == n


def load(ckpt, dtype):
    import torch
    from pipeline.model_gen import load_model
    m = load_model(ROOT / ckpt, torch.device('cpu'))[0].eval()
    return m.to(dtype)


def cast(b, dtype):
    import torch
    return {k: (v.to(dtype) if torch.is_tensor(v) and v.is_floating_point() else v) for k, v in b.items()}


def model_cmp(base, grown, rows_path, prec='fp32', stride=1):
    import torch
    from pipeline.model_gen import CARD_PAD, card_form_of
    torch.set_num_threads(2)
    # fp64 / fp32: both sides in that precision; 64v32: base in fp64, grown in fp32 (base == grown gives the fp32 floor)
    da = torch.float64 if prec in ('fp64', '64v32') else torch.float32
    db = torch.float64 if prec == 'fp64' else torch.float32
    ma, mb = load(base, da), load(grown, db)
    rows = torch.load(rows_path, weights_only=False)[::int(stride)]
    mx = {}
    agree = {'card': 0, 'wait': 0, 'value': 0, 'gate_sign': 0, 'cell': 0}
    n_cell = 0

    def upd(k, v):
        mx[k] = max(mx.get(k, 0.0), float(v))

    t0 = time.time()
    with torch.no_grad():
        for b in rows:
            ba, bb = cast(b, da), cast(b, db)
            ea, eb = ma.encode_gen(ba), mb.encode_gen(bb)
            oa, ob = ma.heads_gen(ea, ba), mb.heads_gen(eb, bb)
            oa = {k: v.double() for k, v in oa.items()}
            ob = {k: v.double() for k, v in ob.items()}
            for k in ('gate', 'value'):
                upd(k + '_logit', (oa[k] - ob[k]).abs().max())
            for k in ('card', 'wait'):
                fin = torch.isfinite(oa[k])
                assert torch.equal(fin, torch.isfinite(ob[k]))
                upd(k + '_logit', (oa[k] - ob[k])[fin].abs().max())
                upd(k + '_logp', (torch.log_softmax(oa[k], -1) - torch.log_softmax(ob[k], -1))[fin].abs().max())
                agree[k] += int(oa[k].argmax() == ob[k].argmax())
            upd('gate_logp', (Fn_logsig(oa['gate']) - Fn_logsig(ob['gate'])).abs().max())
            upd('value_logp', (torch.log_softmax(oa['value'], -1) - torch.log_softmax(ob['value'], -1)).abs().max())
            agree['value'] += int(oa['value'].argmax() == ob['value'].argmax())
            agree['gate_sign'] += int((oa['gate'] > 0) == (ob['gate'] > 0))
            upd('g', g_diff(ea['g'].double(), eb['g'].double()))
            hand = b['hand_card'][0]
            b = ba
            for c in hand[hand != CARD_PAD]:
                card = c.view(1)
                form = card_form_of(b['deck_card'], b['deck_form'], card)
                la, lb = ma.cell_logits_gen(ea, card, form).double(), mb.cell_logits_gen(eb, card, form).double()
                upd('cell_logit', (la - lb).abs().max())
                upd('cell_logp', (torch.log_softmax(la, -1) - torch.log_softmax(lb, -1)).abs().max())
                agree['cell'] += int(la.argmax() == lb.argmax())
                n_cell += 1
    n = len(rows)
    print(f'{prec}: {n} recorded rows, {n_cell} cell-head calls (every real hand card), {time.time() - t0:.0f} s; max |diff| '
          + ', '.join(f'{k} {v:.3g}' for k, v in sorted(mx.items())) + '; argmax agree ' +
          ', '.join(f'{k} {v}/{n_cell if k == "cell" else n}' for k, v in agree.items()))
    return mx, agree, n, n_cell


def Fn_logsig(x):
    import torch
    return torch.nn.functional.logsigmoid(x)


def sym(grown, rows_path):
    """After ONE backward of a policy-like loss on 16 recorded rows: the gradient difference between copy 0 and copy 1 of
    the copied tensors, relative to the gradient size. 0 = the copies are stuck equal (symmetry not broken)."""
    import torch
    torch.set_num_threads(2)
    m = load(grown, torch.float32)
    rows = torch.load(rows_path, weights_only=False)[::100][:16]
    k = m.d // 128
    loss = 0
    for b in rows:
        o = m(b, card=b['hand_card'][:, 0], form=b['hand_form'][:, 0])
        fin = torch.isfinite(o['card'])
        loss = loss + o['gate'].sum() + o['card'][fin].logsumexp(-1) + o['cell'].logsumexp(-1).sum() + o['value'].sum()
    loss.backward()
    for name in ('norm.weight', 'encoder.layers.0.norm1.weight', 'encoder.layers.0.linear2.bias', 'gate_head.weight',
                 'cell_key.weight'):
        p = dict(m.named_parameters())[name]
        g = p.grad
        g0, g1 = (g[:128], g[128:256]) if g.dim() == 1 else (g[..., :128], g[..., 128:256])
        rel = float((g0 - g1).norm() / g.norm().clamp(min=1e-30))
        print(f'{name}: |grad copy0 - copy1| / |grad| = {rel:.3g} (k {k})')


def lat(ckpt, rows_path, device='cpu', threads=2):
    import torch
    from pipeline.model_gen import card_form_of
    torch.set_num_threads(int(threads))
    m = load(ckpt, torch.float32).to(device)
    rows = torch.load(rows_path, weights_only=False)
    rows = [{k: (v.to(device) if torch.is_tensor(v) else v) for k, v in b.items()} for b in rows[::8]]

    def decide(b):
        enc = m.encode_gen(b)
        m.heads_gen(enc, b)
        for j in range(4):
            card = b['hand_card'][:, j]
            m.cell_logits_gen(enc, card, card_form_of(b['deck_card'], b['deck_form'], card))
        if device == 'cuda':
            torch.cuda.synchronize()
    ts = []
    with torch.no_grad():
        for i in range(220):
            t = time.perf_counter()
            decide(rows[i % len(rows)])
            if i >= 20:
                ts.append((time.perf_counter() - t) * 1e3)
    ts.sort()
    n_p = sum(p.numel() for p in m.parameters())
    print(f'{ckpt}: {n_p / 1e6:.2f} M params, {device} threads {threads}: decide-path p50 {ts[len(ts) // 2]:.2f} ms, '
          f'p90 {ts[int(len(ts) * .9)]:.2f}, p99 {ts[int(len(ts) * .99)]:.2f} (200 reps, {len(rows)} distinct rows)')


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    if cmd == 'run':
        run(args[0], args[1], '--rows' in args)
    elif cmd == 'cmp':
        sys.exit(0 if cmp(*args) else 1)
    elif cmd == 'model':                 # exit 1 unless every argmax agrees and (fp64) every |diff| <= 1e-5
        mx, agree, n, n_cell = model_cmp(*args)
        ok = (all(v == (n_cell if k == 'cell' else n) for k, v in agree.items())
              and (len(args) < 4 or args[3] != 'fp64' or max(mx.values()) <= 1e-5))
        print('GROW_IDENTITY', 'PASS' if ok else 'FAIL')
        sys.exit(0 if ok else 1)
    elif cmd == 'sym':
        sym(*args)
    elif cmd == 'lat':
        lat(*args)
