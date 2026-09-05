"""re_range.py <asm> <hex_lo> <hex_hi> -- print asm lines with address in [lo,hi), string refs annotated."""
import re, sys
data = open(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\ext\dump\live\libg_7ad3d8ec7000_rwxp.bin","rb").read()
lo, hi = int(sys.argv[2],16), int(sys.argv[3],16)
for ln in open(sys.argv[1]):
    m = re.match(r"\s*([0-9a-f]+):\s+(.*)", ln)
    if not m: continue
    a = int(m.group(1),16)
    if not (lo <= a < hi): continue
    t = m.group(2).rstrip()
    t = re.sub(r"\s*<\.text\+0x[0-9a-f]+>", "", t)
    mm = re.search(r"# (0x[0-9a-f]+)$", t)
    if mm:
        s = int(mm.group(1),16)
        if s < 0x400000:
            e = data.find(b"\0", s)
            st = data[s:e]
            if 0 < len(st) < 60 and all(32 <= c < 127 for c in st):
                t += f'  "{st.decode()}"'
    print(f"{a:x}: {t}")
