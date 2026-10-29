"""ENG-FIX5: compare the .class entries of two jars (names + sha256 of each entry). python3 jarcmp.py A.jar B.jar"""
import hashlib, sys, zipfile


def entries(p):
    z = zipfile.ZipFile(p)
    return {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/') and 'MANIFEST' not in n}


a, b = entries(sys.argv[1]), entries(sys.argv[2])
only_a = sorted(set(a) - set(b)); only_b = sorted(set(b) - set(a))
diff = sorted(n for n in set(a) & set(b) if a[n] != b[n])
print('entries', len(a), len(b), 'only_a', len(only_a), 'only_b', len(only_b), 'differ', len(diff))
for n in (only_a + only_b + diff)[:20]:
    print(' ', n)
print('IDENTICAL' if not (only_a or only_b or diff) else 'DIFFERENT')
