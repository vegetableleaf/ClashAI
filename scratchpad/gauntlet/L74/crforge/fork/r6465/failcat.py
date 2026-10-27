"""Core test XML results -> totals, failures by exception class, by test class, and the distinct first message lines."""
import glob, sys, collections, xml.etree.ElementTree as ET
t = f = e = s = 0
ex, cls, msg = collections.Counter(), collections.Counter(), collections.defaultdict(list)
for p in glob.glob(sys.argv[1] + '/*.xml'):
    r = ET.parse(p).getroot()
    t += int(r.get('tests')); f += int(r.get('failures')); e += int(r.get('errors')); s += int(r.get('skipped'))
    for tc in r.iter('testcase'):
        for fl in list(tc.iter('failure')) + list(tc.iter('error')):
            typ = (fl.get('type') or '').split('.')[-1]
            m = (fl.get('message') or '').strip().splitlines()[0][:230] if fl.get('message') else ''
            body = fl.text or ''
            cause = next((l.strip() for l in body.splitlines() if l.strip().startswith('Caused by')), '')[:200]
            ex[typ] += 1; cls[tc.get('classname').split('.')[-1]] += 1
            msg[(typ, m, cause)].append(tc.get('classname').split('.')[-1] + ' > ' + tc.get('name')[:120])
print('core tests', t, 'failures', f, 'errors', e, 'skipped', s)
print(ex.most_common()); print(cls.most_common())
for k, v in sorted(msg.items(), key=lambda kv: -len(kv[1])):
    print('\n[%d] %s | %s | %s' % (len(v), *k))
    for x in v[:int(sys.argv[2]) if len(sys.argv) > 2 else 4]:
        print('     ', x)
