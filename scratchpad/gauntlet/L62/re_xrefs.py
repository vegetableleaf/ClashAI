"""re_xrefs.py -- find rodata strings in the live libg code dump and every rip-relative LEA that
references them (x86_64: 48/4C 8D <modrm with mod=00 rm=101> disp32; target = next_ip + disp32).
usage: python re_xrefs.py <bin> <strings...>           (exact NUL-terminated match, case-sensitive)
       python re_xrefs.py <bin> --regex <pattern>      (list matching strings only, no xrefs)
       python re_xrefs.py <bin> --addr <hex_rva>...    (xrefs to arbitrary RVAs)
One pass over the file; RSS ~ file size (26 MB) + tables. stdlib only.
"""
import re, sys, struct

def find_strings(data, names):
    out = {}
    for n in names:
        pat = b"\0" + n.encode() + b"\0"
        pos = data.find(pat)
        hits = []
        while pos != -1:
            hits.append(pos + 1)
            pos = data.find(pat, pos + 1)
        out[n] = hits
    return out

def scan_lea(data, targets):
    """Return {target_rva: [lea_rva,...]} for all rip-relative LEA r64,[rip+disp32]."""
    res = {t: [] for t in targets}
    tset = targets
    n = len(data)
    i = 0
    find = data.find
    # candidate prefixes: 48 8D or 4C 8D
    while True:
        j = find(b"\x8d", i)
        if j == -1 or j + 5 >= n:
            break
        i = j + 1
        if j == 0:
            continue
        rex = data[j - 1]
        if rex not in (0x48, 0x4C):
            continue
        modrm = data[j + 1]
        if (modrm & 0xC7) != 0x05:
            continue
        disp = struct.unpack_from("<i", data, j + 2)[0]
        tgt = (j + 6 + disp) & 0xFFFFFFFFFFFFFFFF
        if tgt in tset:
            res[tgt].append(j - 1)
    return res

def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()
    args = sys.argv[2:]
    if args and args[0] == "--regex":
        rx = re.compile(args[1].encode())
        for m in rx.finditer(data):
            s = m.start()
            # extend to the NUL-delimited string
            a = data.rfind(b"\0", 0, s) + 1
            b = data.find(b"\0", s)
            if b - a < 80:
                print(f"0x{a:x}\t{data[a:b]!r}")
        return
    if args and args[0] == "--call":
        targets = {int(x, 16) for x in args[1:]}
        res = {t: [] for t in targets}
        i = 0
        n = len(data)
        while True:
            j = data.find(b"\xe8", i)
            if j == -1 or j + 5 > n:
                break
            i = j + 1
            rel = struct.unpack_from("<i", data, j + 1)[0]
            tgt = (j + 5 + rel) & 0xFFFFFFFFFFFFFFFF
            if tgt in targets:
                res[tgt].append(j)
        for t in sorted(targets):
            print(f"call 0x{t:x}: {len(res[t])} callers: " + " ".join(f"0x{r:x}" for r in res[t]))
        return
    if args and args[0] == "--addr":
        targets = {int(x, 16) for x in args[1:]}
        names = {t: f"0x{t:x}" for t in targets}
    else:
        found = find_strings(data, args)
        names = {}
        for n, hits in found.items():
            if not hits:
                print(f"{n}: NOT FOUND")
            for h in hits:
                names[h] = n
        targets = set(names)
    res = scan_lea(data, targets)
    for t in sorted(targets):
        refs = res[t]
        print(f"{names[t]} @0x{t:x}: {len(refs)} lea xrefs: " + " ".join(f"0x{r:x}" for r in refs))

if __name__ == "__main__":
    main()
