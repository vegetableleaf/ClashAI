"""Documentation assembly and coverage validation; no experiments or live actions."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
OUT = ROOT / 'CLAUDE_TRANSITION_RECORD_20261006.md'
PARTS = ['OVERVIEW', 'TARGETS', 'METHODS', 'OPERATIONS']
PROTECTED_DIRTY = {'.foreman/codex_autopilot/' + n + '.md'
                   for n in ('BLOCKERS', 'JOURNAL', 'TICKET')}
SECRETS = [r'https://(?:discord(?:app)?\.com)/api/webhooks/\d+/[A-Za-z0-9_-]+',
           r'\b(?:sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{20,})\b']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def decode_text(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16'), 'utf-16 BOM'
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise AssertionError('unreachable encoding fallback')


def clean(data):
    text = decode_text(data)[0].replace('\r\n', '\n').replace('\r', '\n')
    assert not any(re.search(p, text) for p in SECRETS), 'credential literal in selected narrative'
    return text.rstrip('\n') + '\n'


def source_paths():
    paths = set(ROOT.glob('*.md'))
    paths.update((ROOT / '.foreman/codex_autopilot').glob('*.md'))
    paths.update(BASE.rglob('*.md'))
    for directory in ('scratchpad/gauntlet/L68', 'scratchpad/gauntlet/L69',
                      'scratchpad/gauntlet/L70', 'scratchpad/gauntlet/L71',
                      'scratchpad/gauntlet/L72'):
        paths.update((ROOT / directory).rglob('*.md'))
    return sorted(p for p in paths if not p.name.startswith('CLAUDE_TRANSITION_'))


def relocate_links(text, parent):
    def replace(match):
        target = match.group(1)
        if target.startswith(('#', '/', 'http:', 'https:', 'mailto:', 'app:', 'file:')) or ':' in target:
            return match.group(0)
        path, marker, fragment = target.partition('#')
        try:
            moved = (parent / path).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return match.group(0)
        return '](' + moved + (marker + fragment if marker else '') + ')'
    return re.sub(r'\]\(([^)]+)\)', replace, text)


def main():
    assert not OUT.exists(), 'fresh document assembly only'
    now = datetime.now().astimezone().isoformat()
    head = git('rev-parse', 'HEAD').decode().strip()
    pieces, part_bindings = [], []
    for part in PARTS:
        p = BASE / f'CLAUDE_TRANSITION_{part}_20261006.part.md'
        raw = p.read_bytes()
        pieces.append(f'<a id="{part.lower()}"></a>\n\n' + relocate_links(clean(raw), p.parent))
        part_bindings.append(dict(part=part, path=p.relative_to(ROOT).as_posix(), sha256=sha(raw)))
    snapshot = json.loads((BASE / 'CLAUDE_TRANSITION_STOP_SNAPSHOT_20261006.json').read_text())
    assert snapshot['worker_automation']['status'] == 'PAUSED'
    assert snapshot['newsletter_automation']['status'] == 'ACTIVE'
    intro = ('\n## Final documentation snapshot\n\n'
             f'Assembled {now}. Source Git HEAD before final documentation commit: `{head}`.\n'
             'Experimental work is stopped. This snapshot records read-only process and control state; '
             'verify it again before any future action.\n\n```json\n' +
             json.dumps(snapshot, indent=2) + '\n```\n')
    pieces.insert(1, intro)
    paths = source_paths()
    manifest, archives = [], []
    for i, path in enumerate(paths, 1):
        rel = path.relative_to(ROOT).as_posix()
        local = path.read_bytes()
        if rel in PROTECTED_DIRTY:
            raw = git('show', f'HEAD:{rel}')
            origin = f'HEAD@{head}; uncommitted local contents preserved in original file'
        else:
            raw, origin = local, 'worktree snapshot'
        text = clean(raw)
        identity = f'A{i:04d}'
        fence = '~' * max(4, 1 + max([len(x) for x in re.findall(r'~+', text)] or [0]))
        row = dict(id=identity, path=rel, origin=origin, source_sha256=sha(raw),
                   local_file_sha256=sha(local), archived_text_sha256=sha(text.encode()),
                   source_encoding=decode_text(raw)[1], source_bytes=len(raw),
                   archived_lines=len(text.splitlines()))
        manifest.append(row)
        archives.append(f'\n### SOURCE SNAPSHOT {identity}: {rel}\n\n'
                        f'Origin: {origin}. Raw source SHA256: `{row["source_sha256"]}`.\n\n'
                        f'<!-- RECORD_SOURCE {identity} BEGIN -->\n{fence}text\n' + text +
                        f'{fence}\n<!-- RECORD_SOURCE {identity} END -->\n')
    manifest_text = json.dumps(manifest, indent=2)
    index = '\n'.join(f'- {r["id"]}: `{r["path"]}` ({r["archived_lines"]} lines)' for r in manifest)
    pieces.append('\n# Evidence archive and coverage\n\n'
                  f'This appendix contains {len(manifest)} narrative source snapshots, including '
                  'the complete pre-transition HANDOFF.md, HANDOFF_ARCHIVE.md and GAUNTLET_LOG.md, '
                  'all L68–L72 Markdown records, the root brief/overview/reporting/gates, '
                  'and lead rulings. Original numeric evidence '
                  'and receipts remain at the referenced paths.\n\n'
                  'The three unrelated dirty foreman documents are archived from Git HEAD; their '
                  'current local files and hashes are recorded without publishing their uncommitted '
                  'contents. Other unrelated dirty files, the prototype stash and data junctions '
                  'are preserved. No checkpoint, private raw capture, credential or icebow/data '
                  'content is copied into this document.\n\n'
                  'Historical source paragraphs include superseded plans, authority and claims. '
                  'Apply later corrections and the current stop instruction before interpreting them.\n\n'
                  '## Source index\n\n' + index +
                  '\n\n## Machine-readable source coverage manifest\n\n'
                  '<!-- SOURCE_MANIFEST_BEGIN -->\n```json\n' + manifest_text +
                  '\n```\n<!-- SOURCE_MANIFEST_END -->\n')
    pieces.extend(archives)
    log = clean(git('log', '--since=2026-10-04', '--date=iso-strict',
                    '--format=%H | %ad | %s'))
    status = clean(git('status', '--porcelain', '--untracked-files=no'))
    tracked = clean(git('ls-files'))
    pieces.append('\n# Repository continuity inventory\n\n'
                  'This is a path and commit inventory, recorded before the final handoff commit. '
                  'It helps locate code and prior artifacts; source contents remain in the repository. '
                  'Git paths under data do not authorize staging new data.\n\n'
                  '## Commits since October 4\n\n```text\n' + log + '\n```\n'
                  '## Tracked working-tree changes before documentation publication\n\n```text\n' + status +
                  '\n```\n## Tracked repository paths\n\n```text\n' + tracked + '\n```\n')
    document = '\n'.join(pieces)
    OUT.write_text(document, encoding='utf-8')
    # Verify every selected source appears once with its complete normalized payload.
    for row, archive in zip(manifest, archives):
        assert document.count(f'<!-- RECORD_SOURCE {row["id"]} BEGIN -->') == 1
        block = document.split(f'<!-- RECORD_SOURCE {row["id"]} BEGIN -->\n', 1)[1]
        block = block.split(f'<!-- RECORD_SOURCE {row["id"]} END -->', 1)[0]
        lines = block.splitlines(keepends=True)
        payload = ''.join(lines[1:-1])
        assert sha(payload.encode()) == row['archived_text_sha256'], row['path']
        assert archive in document
    assert {r['path'] for r in manifest} == {p.relative_to(ROOT).as_posix() for p in paths}
    assert len(set(r['path'] for r in manifest)) == len(manifest)
    assert not any(re.search(p, document) for p in SECRETS)
    proof = dict(schema=1, time=now, git_head=head, record_path=OUT.name,
                 record_sha256=sha(OUT.read_bytes()), bytes=OUT.stat().st_size,
                 lines=len(document.splitlines()), source_documents=len(manifest),
                 archived_source_lines=sum(r['archived_lines'] for r in manifest),
                 tracked_file_paths=len(tracked.splitlines()),
                 source_coverage_exact=True, source_payload_hashes_exact=True,
                 part_bindings=part_bindings, credentials_scan_matches=0,
                 owner_worker_untouched=True, worker_heartbeat_paused=True,
                 no_experiments_after_replay_completion=True)
    (BASE / 'CLAUDE_TRANSITION_VERIFIED_20261006.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
