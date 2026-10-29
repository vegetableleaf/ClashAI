"""ENG-FIX5: add SME_OWN_BODYPT3 (Skeletons: the 3-body own play keeps its formation's point when >= OWN_BODYPT_D off) to fights.py."""
p = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/parity/fights.py'
s = open(p).read()
a = "OWN_BODYPT_D = 750                                               # units: the Knight back-row clamp moves 500\n"
b = a + "OWN_BODYPT3 = os.environ.get('SME_OWN_BODYPT3', '0') == '1'     # ENG-FIX5, deployments' own-tap pairing (comment there)\n"
assert s.count(a) == 1
s = s.replace(a, b)
a = "                    ev.update(x=round(g['x']), y=round(g['y']), body_moved=[p['x'], p['y']])\n"
b = a + ("                # ENG-FIX5 (SME_OWN_BODYPT3=1, off by default): the same for our Skeletons (3 bodies; the group point is the\n"
         "                # formation's, as for the opponent's first_seen plays). FRESH8 075729@2917: tap (500, 13500), the game's three\n"
         "                # Skeletons at (10001, 7212) / (10500, 8079) / (11002, 7212), deploying, centre (10500, 7500).\n"
         "                elif OWN_BODYPT3 and ev['name'] == 'Skeletons' and len(g['members']) == 3 \\n"
         "                        and math.hypot(g['x'] - p['x'], g['y'] - p['y']) >= OWN_BODYPT_D:\n"
         "                    ev.update(x=round(g['x']), y=round(g['y']), body_moved=[p['x'], p['y']])\n")
assert s.count(a) == 1
s = s.replace(a, b)
open(p, 'w', newline='').write(s)
print('ok')
