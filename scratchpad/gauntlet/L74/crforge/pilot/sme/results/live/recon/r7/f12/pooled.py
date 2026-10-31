import sys
sys.path.insert(0, 'recon')
from r2_tally import cp_lower
from r3_report import sign_p
def row(name, k, n): print('%-10s %d / %d = %.3f  CP low %.3f' % (name, k, n, k / n, cp_lower(k, n)))
n = 88
print('pooled clean-for-RECON-7 FRESH11 + FRESH12 (n 88), counted: pass / strict')
for name, p, s in (('gate', 37 + 29, 34 + 29), ('v3', 36 + 28, 35 + 28), ('RECON-5', 39 + 33, 38 + 32), ('RECON-7', 39 + 34, 38 + 33)):
    row(name + ' pass', p, n); row(name + ' strict', s, n)
# paired (counted) FRESH11: gate vs RECON-5 pass 2:4 strict 0:4; v3 vs RECON-5 0:3 ; FRESH12: gate vs RECON-5 1:5 strict 1:4; v3 vs RECON-5 0:5 strict 0:4 ; RECON-7 vs RECON-5 0:1 / 0:1
print('gate vs RECON-5 pass', (2 + 1, 4 + 5), 'p %.4f' % sign_p(3, 9), '| strict', (0 + 1, 4 + 4), 'p %.4f' % sign_p(1, 8))
print('v3 vs RECON-5 pass', (0, 3 + 5), 'p %.4f' % sign_p(0, 8))
print('v3 vs RECON-7 pass', (0, 3 + 6), 'p %.4f' % sign_p(0, 9))
print('RECON-5 vs RECON-7 pass (0, 1) p %.4f' % sign_p(0, 1))
