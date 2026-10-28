"""Round 8.5: an ability command marked "banner" (hero Goblins) names the side's live GoblinHero_Flag_Building by its
object id, as the game's command does (the goblins it would name are all dead); patched into SmeRun.java and SnapRun2.java."""
import sys
for p in sys.argv[1:]:
    s = open(p, encoding='utf-8').read()
    old_cmd = '''      else if (c.get("kind").asText().equals("skip")) continue;  // a dropped command keeps its index (cmd names)
      else b.useAbility(r, s, c.get("unit").asText(), name);'''
    new_cmd = '''      else if (c.get("kind").asText().equals("skip")) continue;  // a dropped command keeps its index (cmd names)
      else if (c.has("banner")) { banners.add(c); bannerNames.add(name); }  // round 8.5: queued in the tick loop
      else b.useAbility(r, s, c.get("unit").asText(), name);'''
    assert s.count(old_cmd) == 1, p
    s = s.replace(old_cmd, new_cmd)
    old_i = '''    int i = 0;
    for (JsonNode c : plan.get("cmds")) {'''
    assert s.count(old_i) == 1, p
    s = s.replace(old_i, '''    List<JsonNode> banners = new ArrayList<>();
    List<String> bannerNames = new ArrayList<>();
    int i = 0;
    for (JsonNode c : plan.get("cmds")) {''')
    old_loop = '''        if (b.getBattle().getMode().isOver()) break;
        b.getBattle().step();'''
    assert s.count(old_loop) == 1, p
    s = s.replace(old_loop, '''        if (b.getBattle().getMode().isOver()) break;
        queueBanners(b, banners, bannerNames);
        b.getBattle().step();''')
    fn = '''
  // Round 8.5 (A2c): a hero Goblins ability pressed while its banner stands names the banner by object id, as the game's
  // command does (crforge BattleGoblinHeroTest.theBannersAbilitySendsTheSecondWave); by-name it would name the play's
  // dead goblins and be refused. Queued once the side's banner is live and before the run tick; with no banner by run - 1,
  // the by-name command as before.
  static void queueBanners(Standard1v1Battle b, List<JsonNode> cs, List<String> names) {
    int now = b.getBattle().getTick();
    for (int k = 0; k < cs.size(); k++) {
      JsonNode c = cs.get(k);
      if (c == null) continue;
      int g = c.get("given").asInt(), r = c.get("run").asInt(), s = c.get("side").asInt();
      if (now >= r) { cs.set(k, null); continue; }
      int id = -1;
      for (BattleEntity e : b.getBattle().getHolder().entities())
        if (e instanceof WorldEntity we && !(we instanceof TowerEntity) && we.side() == s
            && we.getData().name().equals("GoblinHero_Flag_Building")) id = e.getId();
      if (id >= 0) { b.useAbility(g, r, s, id, names.get(k)); cs.set(k, null); }
      else if (now == r - 1) { b.useAbility(r, s, c.get("unit").asText(), names.get(k)); cs.set(k, null); }
    }
  }

  static String q(String s)'''
    assert s.count('\n  static String q(String s)') == 1, p
    s = s.replace('\n  static String q(String s)', fn, 1)
    open(p, 'w', encoding='utf-8', newline='').write(s)
    print('patched', p)
