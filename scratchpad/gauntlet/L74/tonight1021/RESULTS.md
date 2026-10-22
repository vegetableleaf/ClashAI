### tn_otstart_s74 (10-22 01:15)

```
vs CLX (E4):
std: n=960 A=667 B=681 delta=-1.46 pp [-5.09, +2.17]
fresh: n=960 A=652 B=708 delta=-5.83 pp [-9.42, -2.24]
vs tn_base_s74 (same seed):
std: n=960 A=667 B=663 delta=+0.42 pp [-3.33, +4.16]
fresh: n=960 A=652 B=630 delta=+2.29 pp [-1.53, +6.11]
```
gate: FAIL

### tn_otstart_s75 (10-22 01:26)

```
vs CLX (E4):
std: n=960 A=662 B=681 delta=-1.98 pp [-5.68, +1.72]
fresh: n=960 A=656 B=708 delta=-5.42 pp [-9.01, -1.82]
vs tn_base_s75 (same seed):
std: n=960 A=662 B=714 delta=-5.42 pp [-9.13, -1.70]
fresh: n=960 A=656 B=675 delta=-1.98 pp [-5.60, +1.64]
```
gate: FAIL

### tn_w14_s74 (10-22 01:58)

```
vs CLX (E4):
std: n=960 A=702 B=681 delta=+2.19 pp [-1.47, +5.84]
fresh: n=960 A=686 B=708 delta=-2.29 pp [-5.91, +1.33]
vs tn_base_s74 (same seed):
std: n=960 A=702 B=663 delta=+4.06 pp [+0.46, +7.67]
fresh: n=960 A=686 B=630 delta=+5.83 pp [+2.07, +9.59]
```
gate: FAIL

### tn_otstart_s76 (10-22 02:19)

```
vs CLX (E4):
std: n=960 A=632 B=681 delta=-5.10 pp [-8.88, -1.32]
fresh: n=960 A=641 B=708 delta=-6.98 pp [-10.68, -3.28]
vs tn_base_s76 (same seed):
std: n=960 A=632 B=706 delta=-7.71 pp [-11.60, -3.82]
fresh: n=960 A=641 B=679 delta=-3.96 pp [-7.65, -0.27]
```
gate: FAIL

### tn_bait_s76 (10-22 03:00)

```
vs CLX (E4):
std: n=960 A=716 B=681 delta=+3.65 pp [-0.01, +7.30]
fresh: n=960 A=690 B=708 delta=-1.88 pp [-5.46, +1.71]
vs tn_base_s76 (same seed):
std: n=960 A=716 B=706 delta=+1.04 pp [-2.68, +4.76]
fresh: n=960 A=690 B=679 delta=+1.15 pp [-2.47, +4.76]
```
gate: FAIL

### tn_bait_s75 (10-22 04:42)

```
vs CLX (E4):
std: n=960 A=703 B=681 delta=+2.29 pp [-1.41, +5.99]
fresh: n=960 A=702 B=708 delta=-0.62 pp [-4.20, +2.95]
vs tn_base_s75 (same seed):
std: n=960 A=703 B=714 delta=-1.15 pp [-4.67, +2.37]
fresh: n=960 A=702 B=675 delta=+2.81 pp [-0.81, +6.43]
```
gate: FAIL

### tn_w14_s76 (10-22 05:03)

```
vs CLX (E4):
std: n=960 A=656 B=681 delta=-2.60 pp [-6.36, +1.15]
fresh: n=960 A=651 B=708 delta=-5.94 pp [-9.62, -2.25]
vs tn_base_s76 (same seed):
std: n=960 A=656 B=706 delta=-5.21 pp [-8.80, -1.62]
fresh: n=960 A=651 B=679 delta=-2.92 pp [-6.58, +0.74]
```
gate: FAIL

### tn_w14_s75 (10-22 05:34)

```
vs CLX (E4):
std: n=960 A=659 B=681 delta=-2.29 pp [-6.07, +1.48]
fresh: n=960 A=638 B=708 delta=-7.29 pp [-11.10, -3.49]
vs tn_base_s75 (same seed):
std: n=960 A=659 B=714 delta=-5.73 pp [-9.41, -2.05]
fresh: n=960 A=638 B=675 delta=-3.85 pp [-7.62, -0.09]
```
gate: FAIL

### tn_bait_s74 (10-22 05:35)

```
vs CLX (E4):
std: n=960 A=692 B=681 delta=+1.15 pp [-2.44, +4.74]
fresh: n=960 A=677 B=708 delta=-3.23 pp [-6.85, +0.39]
vs tn_base_s74 (same seed):
std: n=960 A=692 B=663 delta=+3.02 pp [-0.65, +6.69]
fresh: n=960 A=677 B=630 delta=+4.90 pp [+1.18, +8.61]
```
gate: FAIL


## E1 per-play evals vs w7opp (R6 u20), 10-22 07:30 -- G-LOG (log_use/glog_score.py) + win vs CLX / same-seed base

| seed | vs CLX std | vs CLX fresh | vs base std | vs base fresh | hold E1 | hold base | Logs/min E1 |
|---|---|---|---|---|---|---|---|
| 74 | +1.88 [-1.91, +5.66] | +1.77 [-1.96, +5.50] | +2.29 | +2.29 | 0.562 | 0.562 | 1.49 |
| 75 | +3.65 [-0.15, +7.44] | +5.00 [+1.24, +8.76] | +0.21 | +0.73 | 0.524 | 0.583 | 1.69 |
| 76 | +1.56 [-2.21, +5.33] | -0.42 [-4.27, +3.44] | +2.19 | -2.08 | 0.588 | 0.525 | 1.59 |

CLX hold 0.516 (1.62 Logs/min). E1 mean hold 0.558 = base mean 0.557: bait exposure does NOT change the Log habit
(contradicted, measured). All six fail G-LOG1 (< 0.60). Next: E2 = tn_base + shaping tower_crown (tn_tower_s74, pod 32621).
