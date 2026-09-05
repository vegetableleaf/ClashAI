"""re_dis.py -- disassemble a slice of the live libg code dump (RVA-addressed) with the NDK llvm-objdump.
usage: python re_dis.py <hex_rva> <hex_len> [outname]   -> bridge_v2/asm/<rva>_<len>.asm, prints path
"""
import os, subprocess, sys
ROOT = r"C:\Users\benpe\ClashBot\scratchpad\gauntlet"
BIN = os.path.join(ROOT, r"ext\dump\live\libg_7ad3d8ec7000_rwxp.bin")
WRAP = os.path.join(ROOT, r"ext\re\wrap_elf.py")
OUT = os.path.join(ROOT, r"ext\re\bridge_v2\asm")
OBJDUMP = r"C:\Android\Sdk\ndk\27.3.13750724\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-objdump.exe"
rva, ln = sys.argv[1], sys.argv[2]
name = sys.argv[3] if len(sys.argv) > 3 else f"{int(rva,16):x}_{int(ln,16):x}"
elf = os.path.join(OUT, name + ".elf")
asm = os.path.join(OUT, name + ".asm")
subprocess.check_call([sys.executable, WRAP, BIN, rva, ln, elf], stdout=subprocess.DEVNULL)
with open(asm, "w") as f:
    subprocess.check_call([OBJDUMP, "-d", "--x86-asm-syntax=intel", "--no-show-raw-insn", elf], stdout=f)
os.remove(elf)
print(asm)
