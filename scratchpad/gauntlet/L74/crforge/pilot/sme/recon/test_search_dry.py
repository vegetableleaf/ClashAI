"""Dry run of recon_search.search on the laptop: the engine is a STUB that calls a plan exact iff it carries the hand
rule's fix (offline.CASES), else divergent from the gate's first divergence on. Checks the beam loop's mechanics
(edits applied, plans runnable, structural HEAL rule, termination), not the engine's ranking.
    python -I test_search_dry.py  -> 'ok N'"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import offline  # noqa: E402
import recon  # noqa: E402
import recon_search  # noqa: E402
import sme_live  # noqa: E402

N = [0]


def stub(fixed, d, end, detail):
    def an_of(plan, lo=0, hi=10 ** 9):
        good = fixed(plan)
        cls = {t: ('exact' if good or t < d else 'div') for t in range(0, end + 1, 2) if lo <= t <= hi}
        return {'cls': cls, 'first': None if good else d, 'frames': len(cls), 'counts': {}, 'prov': {}}
    sme_live.base_run = lambda plan, frames, me, end_, work, log: ([{'t': 0, 'plan': plan}], an_of(plan))
    recon_search.run_batch = lambda jobs, work: [[{'t': 0, 'plan': json.loads(json.dumps(p))}] for p, _, _ in jobs]
    plans = {}

    def analyse(o, frames, me, lo=0, hi=10 ** 9):
        return an_of(plans[recon_search.key_of(o[0]['plan'])], lo, hi)
    sme_live.analyse = analyse
    sme_live.describe_first = lambda by, frames, me, t: detail
    return plans


def main():
    for fs, run, m, rule, fixed in offline.CASES:
        rec = offline.find(os.path.join(offline.SME, 'engfix', fs, 'inputs_all.jsonl'), m)
        res = offline.find(os.path.join(offline.SME, 'results', 'live', fs, run + '_results.jsonl'), m)
        frames = sme_live.load_frames(os.path.join(offline.SME, 'engfix', fs, 'frames', rec['match'] + '.jsonl'))
        d, end = res['first_div'], max(frames)
        plans = stub(lambda p: bool(fixed(p)), d, end, res['first_detail'])
        # the stub's run_batch returns runnable plans (no _src): map them back to the full plan by key for the predicate
        orig = recon.legal_hypotheses

        def lh(*a, **k):
            hs = orig(*a, **k)
            for _, _, p in hs:
                plans[recon_search.key_of(p)] = p
            return hs
        recon.legal_hypotheses = lh
        best, plan, log = recon_search.search(rec, frames, tempfile.mkdtemp(), beam=4)
        recon.legal_hypotheses = orig
        assert best is not None and fixed(plan), (m, log[:3])
        N[0] += 1
        assert best['an']['first'] is None and len(best['edits']) == 1, (m, best['edits'])
        N[0] += 1
        print(m, 'edits', best['edits'], 'rounds', len(log))
    print('ok', N[0])


if __name__ == '__main__':
    main()
