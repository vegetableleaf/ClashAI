import re, sys
fn = sys.argv[1]
txt = open('webcache/'+fn, encoding='utf-8').read()
print('### VARDEFINES')
for m in re.finditer(r'\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}', txt):
    print(' ', m.group(1), '=', m.group(2))
print('### TABLES (wikitable rows)')
intab=False
for line in txt.split('\n'):
    s=line.strip()
    if s.startswith('{|'): intab=True; print(' --TABLE--'); continue
    if s.startswith('|}'): intab=False; continue
    if intab and (s.startswith('!') or s.startswith('|')):
        print(' ', s[:400])
print('### HISTORY (dated lines)')
for line in txt.split('\n'):
    if re.search(r'\bOn \d{1,2}/\d{1,2}/\d{4}', line) or re.search(r'\(\d{1,2}/\d{1,2}/\d{4}\)', line):
        print(' ', line.strip()[:600])
