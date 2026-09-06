"""One line per checkpoint from eval_s1 outputs. usage: summ_eval.py <eval.out>..."""
import json, sys, os
for fn in sys.argv[1:]:
    print(os.path.basename(fn))
    for l in open(fn):
        if l.startswith('{'):
            d = json.loads(l)
            name = os.path.basename(d['ckpt'].replace(chr(92), '/'))
            extra = ''
            if 'place_hit' in d:
                extra = ' | hit %.4f 1t %.4f dist %.3f' % (d['place_hit'], d['place_1t'], d['place_dist'])
            print('  %-22s ep %2s %-7s half %.4f tile %.4f nll %.3f card %.3f joint %.4f gate_bal %.3f wait %.3f value %.3f%s' % (
                name, d['epoch'], d.get('grid', '?'), d['cell_half_top1'], d['cell_tile_top1'], d['cell_nll'], d['card_top1'],
                d['joint_top1'], d['gate_bal_acc'], d['wait_top1'], d['value_acc'], extra))
