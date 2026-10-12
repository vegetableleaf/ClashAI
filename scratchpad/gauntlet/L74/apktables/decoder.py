"""Offline Supercell table decoding; stdlib only. No game data is bundled."""
from __future__ import annotations

import csv
import hashlib
import io
import lzma
import struct
import zipfile
import zlib
from pathlib import Path, PurePosixPath

MAX_BYTES = 64 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lzma(data: bytes, limit: int) -> bytes:
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO, memlimit=256 * 1024 * 1024)
    out = dec.decompress(data, max_length=limit + 1)
    if len(out) > limit:
        raise ValueError('decoded size exceeds limit')
    if not dec.eof:
        raise ValueError('truncated LZMA stream')
    if dec.unused_data:
        raise ValueError('trailing LZMA bytes')
    return out


def decode(raw: bytes, limit: int = MAX_BYTES) -> tuple[bytes, str]:
    """Plain UTF-8, standard LZMA/XZ, SC 9-byte LZMA, or SC v1 zlib.

    SC v1 wrapper: SC + big-endian version(1) + MD5 length(16) + MD5
    + zlib payload. Other SC wrapper versions fail explicitly.
    """
    if len(raw) > limit:
        raise ValueError('input size exceeds limit')
    if raw.startswith(b'SC'):
        if len(raw) < 10:
            raise ValueError('truncated SC header')
        version, hlen = struct.unpack('>II', raw[2:10])
        if version != 1 or hlen != 16 or len(raw) < 26:
            raise ValueError(f'unsupported SC wrapper version={version} hash_length={hlen}')
        dec = zlib.decompressobj()
        out = dec.decompress(raw[26:], limit + 1)
        if len(out) > limit or not dec.eof or dec.unused_data:
            raise ValueError('invalid or oversized SC zlib payload')
        if hashlib.md5(out).digest() != raw[10:26]:
            raise ValueError('SC MD5 mismatch')
        return out, 'sc-v1-zlib'
    errors = []
    if raw.startswith(b'\xfd7zXZ\x00') or (len(raw) >= 5 and raw[0] <= 224 and b'\x00' in raw[:5]):
        try:
            return _lzma(raw, limit), 'lzma-standard'
        except (lzma.LZMAError, ValueError) as e:
            errors.append(str(e))
        if len(raw) >= 9:
            size = int.from_bytes(raw[5:9], 'little')
            if size <= limit:
                # Some producers retain an EOS marker and require unknown-size
                # ALONE framing. Both encodings must match the SC declared size.
                for declared in (size, 0xffffffffffffffff):
                    try:
                        out = _lzma(raw[:5] + struct.pack('<Q', declared) + raw[9:], limit)
                        if len(out) != size:
                            raise ValueError(f'LZMA size mismatch: expected {size}, got {len(out)}')
                        return out, 'sc-lzma-9'
                    except (lzma.LZMAError, ValueError) as e:
                        errors.append(str(e))
        raise ValueError('LZMA decode failed: ' + '; '.join(errors))
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise ValueError('unsupported binary/compression header: ' + raw[:12].hex()) from e
    if '\x00' in text or any(ord(c) < 32 and c not in '\r\n\t' for c in text):
        raise ValueError('binary control bytes in plain table')
    return raw, 'plain-utf8'


def extract(apk_dir: Path, dest: Path) -> dict:
    """Inventory all splits; never ZIP-extract arbitrary paths or resolve conflicts silently."""
    apks = sorted(apk_dir.glob('*.apk'))
    if not apks:
        raise ValueError(f'no APKs in {apk_dir}')
    manifest = dict(apks=[], files={}, failures=[], conflicts=[])
    for apk in apks:
        h = hashlib.sha256()
        with apk.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        manifest['apks'].append(dict(name=apk.name, sha256=h.hexdigest(), bytes=apk.stat().st_size))
        with zipfile.ZipFile(apk) as z:
            for info in z.infolist():
                parts = PurePosixPath(info.filename).parts
                if not (len(parts) >= 3 and parts[0] == 'assets' and
                        parts[1].startswith('csv_') and Path(parts[-1]).suffix.lower() in ('.csv', '.toml')):
                    continue
                entry = dict(apk=apk.name, member=info.orig_filename)
                try:
                    if '..' in parts or '\\' in info.orig_filename or ':' in info.orig_filename or '\x00' in info.orig_filename:
                        raise ValueError('unsafe archive path')
                    if info.file_size > MAX_BYTES:
                        raise ValueError('archive member exceeds limit')
                    raw = z.read(info)
                    data, codec = decode(raw)
                    data.decode('utf-8-sig')
                    rel = '/'.join(parts[1:])
                    entry.update(input_sha256=sha(raw), sha256=sha(data), bytes=len(data), codec=codec)
                    if rel in manifest['files']:
                        old = manifest['files'][rel]
                        if old['sha256'] != entry['sha256']:
                            manifest['conflicts'].append(dict(path=rel, first=old, second=entry))
                        else:
                            old.setdefault('duplicates', []).append(entry)
                        continue
                    path = dest / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    manifest['files'][rel] = entry
                except (ValueError, lzma.LZMAError, zlib.error, UnicodeError, zipfile.BadZipFile) as e:
                    manifest['failures'].append(dict(**entry, error=str(e)))
    if not manifest['files'] and not manifest['failures']:
        raise ValueError('no CSV/TOML table assets found')
    manifest['fingerprint'] = sha(repr([(a['name'], a['sha256']) for a in manifest['apks']]).encode())
    return manifest


def csv_records(data: bytes) -> dict:
    """Read the two-header SC CSV layout, preserving continuation row positions."""
    rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))
    if len(rows) < 2 or not rows[0] or rows[0][0] != 'Name':
        raise ValueError('expected Name header and type row')
    columns, types = rows[:2]
    result, current = {}, None
    for values in rows[2:]:
        if not any(values):
            continue
        values += [''] * (len(columns) - len(values))
        if len(values) != len(columns):
            raise ValueError('CSV column count mismatch')
        record = {}
        for i, (k, v) in enumerate(zip(columns, values)):
            if not v:
                record[k] = None
            elif i < len(types) and types[i].lower() in ('int', 'integer'):
                record[k] = int(v)
            else:
                record[k] = v
        if values[0]:
            if values[0] in result:
                raise ValueError('duplicate CSV Name: ' + values[0])
            current = []
            result[values[0]] = current
        if current is None:
            raise ValueError('orphan CSV continuation')
        current.append(record)
    return result
