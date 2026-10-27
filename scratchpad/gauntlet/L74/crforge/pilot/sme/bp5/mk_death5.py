"""A2c-BP5: death5.py from bp4/death_census.py: AimRun8 (hit / rm observer events) on a lib with fork patch 0005 (MoveProbe
'dmg': target, attacker, damage, died). Per row also: kind (dmg = a direct hit, typed, proj, none) and killer (the attacker of
the hit that killed R at t), killer_name, killer_is_u, the order within step t of U's first event, the killer's first event and
the killing hit (u_idx, k_idx, hit_idx), and U's / R's index in the C list (holder order) at t-1 (u_h, r_h, k_h)."""
import sys
s = open(sys.argv[1]).read()
s = s.replace("'/workspace/pilot/bp4/work/death'", "'/workspace/pilot/bp5/work/death5'")
s = s.replace("lib + '/*:/workspace/pilot/bp4/build_aim4', 'AimRun4'", "lib + '/*:/workspace/pilot/bp5/build_aim8', 'AimRun8'")
a = "    C, PA = {}, {}\n"
b = "    C, PA, EV = {}, {}, {}\n"
assert s.count(a) == 1; s = s.replace(a, b)
a = "        PA[o['t']] = o.get('PA', [])  # [id, 'P'|'A', name, side, x, y]\n"
b = a + "        EV[o['t']] = o['ev']\n"
assert s.count(a) == 1; s = s.replace(a, b)
a = "                   'u_before_r': u < r}\n"
b = """                   'u_before_r': u < r}
            ev = EV.get(t, [])
            first = lambda i: next((k for k, e in enumerate(ev) if e[0] in ('prop', 'disp', 'replan') and e[1] == i), None)
            kd = next(((k, e) for k, e in enumerate(ev) if e[0] == 'dmg' and e[1] == r and e[4] == 1), None)
            kh = next(((k, e) for k, e in enumerate(ev) if e[0] == 'hit' and e[1] == r and e[4] == 1), None)
            killer = kd[1][2] if kd else (kh[1][2] if kh and kh[1][5] == 1 else None)
            hold = list(prev)
            row.update({'kind': 'dmg' if kd else ('typed' if kh and kh[1][5] == 1 else 'proj' if kh and kh[1][5] == 2 else 'none'),
                        'killer': killer, 'killer_name': prev.get(killer, [0, '?'])[1] if killer is not None else None,
                        'killer_is_u': killer == u, 'u_idx': first(u), 'k_idx': first(killer) if killer is not None else None,
                        'hit_idx': kd[0] if kd else (kh[0] if kh else None),
                        'u_h': hold.index(u), 'r_h': hold.index(r), 'k_h': hold.index(killer) if killer in prev else None})
"""
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
