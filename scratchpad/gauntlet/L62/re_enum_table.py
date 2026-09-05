"""re_enum_table.py -- extract (string -> enum value) pairs from a Supercell string->enum parser
(pattern: lea rsi,[rip+str]; mov rdi,rbx; call strcmp; mov ecx,eax; mov eax,IMM; test cl,cl; jne ret).
usage: python re_enum_table.py <asm file>
"""
import re, sys
BIN = r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\ext\dump\live\libg_7ad3d8ec7000_rwxp.bin"
data = open(BIN, "rb").read()
lines = open(sys.argv[1]).read().splitlines()
addr_of = {}
ins = []
for ln in lines:
    m = re.match(r"\s*([0-9a-f]+):\s+(.*)", ln)
    if m:
        addr_of[int(m.group(1), 16)] = len(ins)
        ins.append((int(m.group(1), 16), m.group(2).strip()))
def cstr(a):
    e = data.find(b"\0", a)
    return data[a:e].decode("latin1")
def first_mov_eax(i, depth=0):
    while i < len(ins) and depth < 40:
        a, t = ins[i]
        m = re.match(r"mov\s+eax, (0x[0-9a-f]+|-?\d+)", t)
        if m:
            v = int(m.group(1), 0)
            return v if v < 0x80000000 else v - 0x100000000
        m = re.match(r"jmp\s+(0x[0-9a-f]+)", t)
        if m:
            tgt = int(m.group(1), 16)
            if tgt in addr_of:
                i = addr_of[tgt]; depth += 1; continue
            return None
        if t.startswith("ret") or t.startswith("lea\trsi") or t.startswith("lea rsi"):
            return None
        i += 1
    return None
for i, (a, t) in enumerate(ins):
    m = re.match(r"lea\s+rsi, \[rip [-+] 0x[0-9a-f]+\]\s+# (0x[0-9a-f]+)", t)
    if m:
        s = cstr(int(m.group(1), 16))
        print(f"{a:x}\t{s!r}\t-> {first_mov_eax(i + 1)}")
