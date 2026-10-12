"""Read-only source/receipt audit. No runtime activation, network or Git writes."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def main():
    receipt = json.loads((HERE/'merge_receipt.json').read_text())
    assert git('branch', '--show-current') == 'l74-newsim'
    assert git('rev-parse', 'HEAD') == receipt['head']
    assert git('rev-parse', 'l74-adapt2') == receipt['incoming']
    incoming = git('diff', '--name-only', receipt['base'], receipt['incoming']).splitlines()
    custom = {'pipeline/e1_eval.py', 'pipeline/rl_royale.py', 'pipeline/rl_royale.yaml', 'pipeline/royale_runtime.py'}
    for path in incoming:
        data = (ROOT/path).read_bytes()
        text = data.decode('utf8', errors='replace')
        assert not any(line.startswith(('<<<<<<< ', '>>>>>>> ')) or line == '======='
                       for line in text.splitlines()), path
        if path not in custom:
            expected = subprocess.check_output(['git', 'show', f"{receipt['incoming']}:{path}"], cwd=ROOT)
            assert data.replace(b'\r\n', b'\n') == expected.replace(b'\r\n', b'\n'), f'incoming branch content changed: {path}'
        if path.endswith('.py'):
            ast.parse(text, filename=path)
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    assert not git('diff', '--name-only', '--', 'pipeline/live_options.py',
                   'scratchpad/gauntlet/L70/live', 'scratchpad/gauntlet/L68/live_reader')
    receipt.update(incoming_paths=incoming, incoming_path_count=len(incoming),
        source_integration_verified=True,
        conflict_resolution='Union runtime selectors: preserve 20261012 Hero IW checks and ADAPT unpinned-linux opt-in; unset defaults unchanged.',
        metadata_blocker='Git ORIG_HEAD.lock is under protected linked-worktree metadata. No merge commit or index write.',
        live_paths_changed=False)
    (HERE/'merge_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    files = [ROOT/p for p in incoming] + list(HERE.glob('*.py')) + [HERE/'run_newsim.sh']
    rows = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in dict.fromkeys(files)]
    (HERE/'source_receipt.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(f'NEWSIM_SOURCE_OK: {len(incoming)} incoming paths integrated; live paths unchanged; Python syntax valid')


if __name__ == '__main__':
    main()
