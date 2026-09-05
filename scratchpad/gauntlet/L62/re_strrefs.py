"""re_strrefs.py <asm> -- annotate: print every rip-relative reference in an asm file that points at a
printable NUL-terminated string in the code dump (address, string)."""
import re, sys
data = open(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\ext\dump\live\libg_7ad3d8ec7000_rwxp.bin","rb").read()
for ln in open(sys.argv[1]):
    m = re.search(r"^\s*([0-9a-f]+):.*# (0x[0-9a-f]+)", ln)
    if m:
        a = int(m.group(2),16)
        if a < 0x400000:
            e = data.find(b"\0", a)
            s = data[a:e]
            if 0 < len(s) < 80 and all(32 <= c < 127 for c in s):
                print(m.group(1), s.decode())
