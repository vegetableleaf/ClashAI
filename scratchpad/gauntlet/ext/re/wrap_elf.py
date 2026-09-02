"""Wrap a byte range of a section-less ELF (libg.so has no .text header, so llvm-objdump refuses
--start-address) into a minimal ELF64 with one .text section at the original virtual address, so
`llvm-objdump -d wrapped.elf` disassembles it with correct addresses. Dependency-free on purpose.
usage: python wrap_elf.py <src.so> <hex_vaddr> <hex_len> <out.elf>   (file offset == vaddr for libg's first PT_LOAD)
"""
import struct, sys

src, vaddr, length, out = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16), sys.argv[4]
with open(src, "rb") as f:
    f.seek(vaddr)
    code = f.read(length)
shstrtab = b"\0.text\0.shstrtab\0"
ehsize, shentsize = 64, 64
code_off = ehsize
shstr_off = code_off + len(code)
shoff = shstr_off + len(shstrtab)
shoff += (-shoff) % 8
ehdr = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\0" * 8
ehdr += struct.pack("<HHIQQQIHHHHHH", 3, 62, 1, vaddr, 0, shoff, 0, ehsize, 0, 0, shentsize, 3, 2)
def sh(name, typ, flags, addr, off, size, align):
    return struct.pack("<IIQQQQIIQQ", name, typ, flags, addr, off, size, 0, 0, align, 0)
shdrs = sh(0, 0, 0, 0, 0, 0, 0) + sh(1, 1, 0x6, vaddr, code_off, len(code), 16) + sh(7, 3, 0, 0, shstr_off, len(shstrtab), 1)
blob = ehdr + code + shstrtab
blob += b"\0" * (shoff - len(blob)) + shdrs
with open(out, "wb") as f:
    f.write(blob)
print(f"wrote {out}: {len(code)} code bytes at 0x{vaddr:x}")
