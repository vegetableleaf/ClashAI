"""Ticket-scoped offline checks with receipts. Never executes an engine or network."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    for name in ('fork','tests','selection','contract'): ap.add_argument('--'+name, action='store_true')
    a = ap.parse_args()
    receipt = HERE/'verification.json'
    evidence = json.loads(receipt.read_text()) if receipt.exists() else {}
    if a.fork:
        src = ROOT/'research/ext/Royale/RoyaleSim'
        def git(*args): return subprocess.check_output(['git','-C',str(src),*args],text=True).strip()
        assert git('branch','--show-current') == 'clashbot'
        assert git('rev-parse','HEAD') == git('rev-parse','origin/HEAD')
        assert not git('status','--porcelain','--untracked-files=no')
        evidence['fork'] = dict(head=git('rev-parse','HEAD'), upstream=git('symbolic-ref','refs/remotes/origin/HEAD'),
                                patches=git('rev-list','--count','origin/HEAD..HEAD'))
        print('PARITY_FORK_PASS')
    if a.tests:
        cmd = [sys.executable,'-m','pytest',str(HERE/'tests'),'-q','-p','no:cacheprovider','-p','no:tmpdir']
        p = subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        output = p.stdout+p.stderr
        print(output)
        evidence['tests'] = dict(command=cmd, cwd=str(ROOT), exit_code=p.returncode,
                                 output_sha256=hashlib.sha256(output.encode()).hexdigest(), output=output)
        receipt.write_text(json.dumps(evidence,indent=2)+'\n')
        if p.returncode: raise SystemExit(p.returncode)
        print('PARITY_TESTS_PASS')
    if a.selection:
        from scratchpad.gauntlet.L74.parity.core import select, ps
        start = time.monotonic()
        cohort, excluded = select(ps.LIVE, limit=100, assumed_level=15)
        assert len(cohort) == 100
        assert len({r['match'] for r in cohort}) == 100
        assert all(len(r['sha256']) == 64 and r['frames'] for r in cohort)
        evidence['selection'] = dict(selected=len(cohort), excluded=len(excluded), seconds=time.monotonic()-start,
            deck_complete_candidates=sum(not r['blocks'] for r in cohort),
            blockers=dict(Counter(b for r in cohort for b in r['blocks'])),
            decisions=sum(len(r['frames']) for r in cohort), plays=sum(len(r['plays']) for r in cohort),
            own_plays=sum(p['source']=='confirmed_own_tap' for r in cohort for p in r['plays']),
            proxy_enemy_plays=sum(p['source']=='first_seen_body_proxy' for r in cohort for p in r['plays']),
            cohort_sha256=hashlib.sha256(json.dumps([(r['match'],r['sha256']) for r in cohort]).encode()).hexdigest(),
            matches=[dict(match=r['match'],sha256=r['sha256'],blocks=r['blocks']) for r in cohort])
        print('PARITY_SELECTION_PASS')
    if a.contract:
        for p in HERE.rglob('*.py'):
            if 'output' not in p.parts: ast.parse(p.read_text(encoding='utf8'),filename=str(p))
        build=(HERE/'build_fork.sh').read_text(); run=(HERE/'run_parity.sh').read_text()
        assert '--offline' in build and '--no-index' in build and '--no-default-features' in build
        assert 'tools/stage_wheel_data.py' in build and '--locked' in build
        assert 'cpu.lock' in run and 'WORKERS <= 24' in run and 'SUMMARY.txt' in run and '/DONE' in run
        assert '--runtime old new fork' in run and 'MATCHES:-100' in run
        assert 'Parity-Evidence:' in (HERE/'FORK.md').read_text()
        evidence['contract'] = dict(python_syntax='passed', shell_source='reviewed; Bash execution pending',
                                     files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir()
                                            if p.suffix in ('.py','.sh')})
        print('PARITY_CONTRACT_PASS')
    assert not any(k.split('.')[0] in ('royalesim','royalegym') for k in sys.modules)
    receipt.write_text(json.dumps(evidence,indent=2)+'\n')


if __name__ == '__main__': main()
