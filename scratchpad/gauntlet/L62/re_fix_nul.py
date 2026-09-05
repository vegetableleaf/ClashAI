import sys
p = sys.argv[1]
d = open(p, 'rb').read()
d = d.replace(b"'\x00'", b"'\\0'")
open(p, 'wb').write(d)
print(d.count(b'\x00'))
