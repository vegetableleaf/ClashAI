// F1 (plan1026 Pillar 1 Stage 2): one crforge match behind RoyaleSim's engine-core seam, for pipeline/crforge_core.py.
// D1-C: tower troops (reset with a spawn group per side).
// Built against crforge core @ ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0. Match setup as LadderEnv.reset / CfSpeed.Match
// (addPlayerData x2, startLadderMatch), plays through PlayerCommands.playCard, ability presses through useAbility.
// state() writes RoyaleSim's state_json shape (royalegym.protocol.BattleState; entities / spells / projectiles as
// positional arrays) in RoyaleSim's units: positions x18 (18,000 subtiles per tile vs crforge's 1,000), elixir in milli.
//
// Body identity: crforge names every unit after the play that made it ("c5_0", a spawn "c5_0_3"), so the spawning
// card of ANY body is the card of its root play (the name before the first '_'), which this class records as it gives
// plays. Python pushes body_map.json: name -> entry (unique names) and name|root card -> entry (by_name_unique false).
// Spell objects: Python pushes object name -> (card id, motion) from crforge's own card table chains.
//
// save() / load(): crforge's DeepCopy of the match state (battle, commands, this class's play log), sharing only the
// game tables' objects and the rarity tables, as LadderEnv.fork does. A snapshot is never stepped: load copies it again,
// so one snapshot gives any number of independent forks.

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.match.LadderMatch;
import org.crforge.core.battle.match.MatchSide;
import org.crforge.core.battle.projectile.ProjectileEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.battle.spawn.SpawnHost;
import org.crforge.core.battle.deploy.PlacementSearch;
import org.crforge.core.pathfinding.GridEntity;
import org.crforge.core.pathfinding.GridEntityState;
import org.crforge.core.pathfinding.grid.PathfindingGlobals;
import org.crforge.core.pathfinding.combat.HitPoints;
import org.crforge.core.pathfinding.combat.RarityTable;
import org.crforge.core.pathfinding.target.SightRange;
import org.crforge.core.pathfinding.target.TargetView;
import org.crforge.core.pathfinding.target.TargetingState;
import org.crforge.core.util.DeepCopy;

public final class CfCore {
  public static final int K = 18, NONE = -1;

  /** Everything one match is: what save() copies. */
  public static final class St {
    Standard1v1Battle std;
    PlayerCommands cmds;
    int cmdN;
    final HashMap<String, String> playCard = new HashMap<>();   // play / entity name -> the card it came from
    final HashMap<String, Integer> unresolved = new HashMap<>();   // diagnostics: creations no card was found for
    int[][] levels = new int[2][8];
    int[][] deckIds = new int[2][8];
    int[][] forms = new int[2][8];
    int[][] towerMax = new int[2][3];
    // RoyaleSim ability button b of a side = crforge champion slot buttons[side][b] (1 or 2): RoyaleSim lists heroes,
    // then champions; crforge numbers its slots from the highest deck index down (Standard1v1Battle's deal).
    int[][] buttons = new int[2][0];
    int[][] abilityRun = {{-1, -1}, {-1, -1}};   // run tick of the button's last given press

    /** The card an entity name descends from: itself if recorded, else its root ("c5_0_3" -> c5, "proj_9_0" -> proj_9). */
    String cardOfName(String nm) {
      String c = playCard.get(nm);
      if (c != null) return c;
      int cut = nm.indexOf('_', nm.startsWith("proj_") ? 5 : 0);
      return cut < 0 ? null : playCard.get(nm.substring(0, cut));
    }
  }

  final GameTables tables;
  final Set<Object> shared;
  public St s;
  // identity tables (Python fills them; packed entry = cardId << 8 | status flags)
  public final HashMap<String, Integer> unique = new HashMap<>();
  public final HashMap<String, String> uniqueCard = new HashMap<>();
  public final HashMap<String, Integer> byRoot = new HashMap<>();
  public final HashMap<String, Integer> spellObj = new HashMap<>();   // object name -> cardId << 4 | motion
  // unit type ids are per JVM, not per core: a fork loaded into a fresh core must number its bodies the same
  public static final LinkedHashMap<String, Integer> unitType = new LinkedHashMap<>();
  public final Map<String, Integer> missing = new ConcurrentHashMap<>();   // "body|root card" / "area:name" -> count
  public final Map<String, Integer> stats = new ConcurrentHashMap<>();
  public String[] cardNames = new String[0];   // RoyaleSim catalogue id -> name

  public CfCore(GameTables tables) {
    this.tables = tables;
    this.shared = DeepCopy.reachable(tables);
  }

  static void bump(Map<String, Integer> m, String k) { m.merge(k, 1, Integer::sum); }

  public Map<String, Integer> unresolved() { return s.unresolved; }

  /** Decks by card row name in deal order (hand = 0..3, queue 4..7: RoyaleSim ShuffleMode.NONE), forms 0/1/2. */
  public void reset(int seed, String[] d0, int[] f0, String[] d1, int[] f1, int[] lv0, int[] lv1, int tl0, int tl1,
      int[] ids0, int[] ids1) {
    reset(seed, d0, f0, d1, f1, lv0, lv1, tl0, tl1, ids0, ids1, Standard1v1Battle.PRINCESS_TOWERS,
        Standard1v1Battle.PRINCESS_TOWERS);
  }

  /**
   * D1-C: each side's towers from its own spawn group (crforge's tower selections: King_PrincessTowers,
   * King_CannonTowers, King_KnifeTowers = Dagger Duchess, King_ChefTowers = Royal Chef), king and princess slots at
   * the side's tower level. A tower troop is a TowerEntity like a princess tower, so state() reports it the same way.
   */
  public void reset(int seed, String[] d0, int[] f0, String[] d1, int[] f1, int[] lv0, int[] lv1, int tl0, int tl1,
      int[] ids0, int[] ids1, String g0, String g1) {
    St n = new St();
    n.std = new Standard1v1Battle(tables, List.of(new Standard1v1Battle.Towers(g0, tl0, tl0),
        new Standard1v1Battle.Towers(g1, tl1, tl1)), true);
    n.std.getWorld().seed(seed);
    n.std.addPlayerData(1);
    n.std.addPlayerData(1);
    n.std.startLadderMatch(Arrays.asList(d0), Arrays.asList(d1), 0, 0, f0.clone(), f1.clone());
    // crforge dealt with its own seeded shuffle (its draws stay taken); the deal is put back in the setup's order
    int[] places = {0, 1, 2, 3, 4, 5, 6, 7}, cards = {0, 1, 2, 3, 4, 5, 6, 7};
    for (int side = 0; side < 2; side++) {
      n.std.getMatch().side(side).getHand().rearrange(places, cards);
      int[] h = n.std.getMatch().side(side).getHand().slots();
      List<Integer> q = n.std.getMatch().side(side).getHand().queue();
      for (int k = 0; k < 8; k++)
        if ((k < 4 ? h[k] : q.get(k - 4)) != k) throw new IllegalStateException("deal not in setup order: side " + side);
    }
    n.cmds = new PlayerCommands(n.std);
    n.std.getWorld().addObserver(new Origin(n, spellObj, cardNames));
    n.levels = new int[][] {lv0.clone(), lv1.clone()};
    n.deckIds = new int[][] {ids0.clone(), ids1.clone()};
    n.forms = new int[][] {f0.clone(), f1.clone()};
    for (int side = 0; side < 2; side++) {
      TowerEntity king = n.std.getWorld().kingTower(side);
      List<Integer> bs = new ArrayList<>();
      for (int slot = 1; slot <= 2; slot++) if (king.championSlot(slot).getChampion() != null) bs.add(slot);
      final int sd = side;
      // ponytail: fixed at the deal; a slot crforge reassigns mid-match (allowsReassignment) keeps its button
      bs.sort(Comparator.comparingInt(sl -> {
        int idx = king.championSlot(sl).getDeckIndex();
        return (n.forms[sd][idx] == 2 ? 0 : 8) + idx;
      }));
      n.buttons[side] = bs.stream().mapToInt(Integer::intValue).toArray();
    }
    s = n;
    for (BattleEntity e : s.std.getBattle().getHolder().entities())
      if (e instanceof TowerEntity t) s.towerMax[t.side()][towerSlot(t)] = t.getHitPoints().getMaximum();
  }

  public boolean over() { return s.std.getBattle().getMode().isOver(); }
  public int tick() { return s.std.getBattle().getTick(); }

  public void step(int ticks) {
    for (int t = 0; t < ticks && !over(); t++) s.std.getBattle().step();
  }

  /**
   * What each entity a name does not trace to a play came from, as crforge's world observer reports it at creation:
   * a projectile ("proj_N": its spell card, else its firer's card) and an area effect ("Rage_812": its spell card,
   * else the card of its source -- the dying body, the chaining area, the casting play). Recorded in the match's play
   * log, so bodies named after a projectile ("proj_N_0", the Barbarian Barrel's barbarian) and areas resolve, and a
   * save carries it. Lives in St: DeepCopy copies the observer with the world.
   */
  public static final class Origin implements WorldObserver {
    final St st;
    final HashMap<String, Integer> spellObj;
    final String[] cardNames;

    Origin(St st, HashMap<String, Integer> spellObj, String[] cardNames) {
      this.st = st; this.spellObj = spellObj; this.cardNames = cardNames;
    }

    /** The card of what made an entity: a spell object's card, a recorded name's, a body's root play's. */
    String cardOf(Object src) {
      if (src instanceof ProjectileEntity p) {
        Integer so = spellObj.get(p.getData().name());
        if (so != null) return cardNames[so >> 4];
        String c = st.cardOfName(p.name());
        if (c == null && p.getOwner() != null) c = st.cardOfName(p.getOwner().name());
        if (c == null && p.getRoot() != null) c = st.cardOfName(p.getRoot().name());
        return c != null || p.getAreaLauncher() == null ? c : cardOf(p.getAreaLauncher());
      }
      if (src instanceof AreaEffectEntity a) {
        Integer so = spellObj.get(a.getData().name());
        return so != null ? cardNames[so >> 4] : st.cardOfName(a.name());
      }
      return src instanceof WorldEntity w ? st.cardOfName(w.name()) : null;
    }

    void note(String name, String card) { if (card != null) st.playCard.putIfAbsent(name, card); }

    @Override public void projectileLaunched(int tick, ProjectileEntity p) { note(p.name(), cardOf(p)); }

    @Override public void deathProjectileLaunched(int tick, WorldEntity dying, ProjectileEntity p) {
      note(p.name(), st.cardOfName(dying.name()));
    }

    @Override public void actionProjectileLaunched(int tick, WorldEntity owner, String action, int phase, ProjectileEntity p) {
      note(p.name(), st.cardOfName(owner.name()));
    }

    @Override public void characterSpawned(int tick, SpawnHost source, CharacterEntity child, int x, int y) {
      note(child.name(), cardOf(source));
    }

    @Override public void projectileAreaEffect(int tick, ProjectileEntity p, AreaEffectEntity a) {
      String card = cardOf(p);
      if (card != null) st.playCard.put(a.name(), card);
    }

    @Override public void areaEffectCreated(int tick, AreaEffectEntity a, String how, String source) {
      Integer so = spellObj.get(a.getData().name());
      String card = so != null ? cardNames[so >> 4] : source == null ? null : st.cardOfName(source);
      if (card == null) bump(st.unresolved, "area_src:" + a.getData().name() + "|" + how + "|" + String.valueOf(source).replaceAll("[0-9]+", "#"));
      note(a.name(), card);
    }
  }

  String rootCard(String nm) { return s.cardOfName(nm); }

  int level(int side, int slot) {
    int[] h = s.std.getMatch().side(side).getHand().slots();
    return slot >= 0 && slot < 4 && h[slot] >= 0 ? s.levels[side][h[slot]] : 16;
  }

  /** [refusal ordinal (0 = given; 100 = a play crforge does not model), resolved x, resolved y] in crforge units. */
  public int[] play(int side, int slot, int x, int y) {
    if (over()) return new int[] {PlayerCommands.Refusal.MATCH_OVER.ordinal(), x, y};
    String name = "c" + (s.cmdN++);
    try {
      int[] h = s.std.getMatch().side(side).getHand().slots();
      String card = h[slot] >= 0 ? s.std.getMatch().side(side).deck().get(h[slot]).name() : null;
      PlayerCommands.Giving g = s.cmds.playCard(side, slot, level(side, slot), x, y, name);
      if (g.given()) s.playCard.put(name, card);
      return new int[] {g.refusal().ordinal(), g.given() ? g.x() : x, g.given() ? g.y() : y};
    } catch (UnsupportedOperationException e) {
      bump(stats, "unsupported_play");
      return new int[] {100, x, y};
    }
  }

  public int check(int side, int slot) {
    if (over()) return PlayerCommands.Refusal.MATCH_OVER.ordinal();
    try { return s.cmds.tryCard(side, slot, level(side, slot)).refusal().ordinal(); }
    catch (UnsupportedOperationException e) { return 100; }
  }

  /**
   * A press of RoyaleSim ability button ``button`` (St.buttons: the king's champion slot); the refusal ordinal. While
   * a press of the button waits its 20 ticks the button refuses (ABILITY_PENDING), as RoyaleSim fin16 under a 20-tick
   * command delay does (CARD_PENDING until the run, F1c-1 abil_repress.py); crforge's PlayerCommands would give it.
   */
  public int ability(int side, int button, boolean dry) {
    if (over()) return PlayerCommands.Refusal.MATCH_OVER.ordinal();
    if (button < 0 || button >= s.buttons[side].length) return PlayerCommands.Refusal.NO_CHAMPION.ordinal();
    if (s.abilityRun[side][button] >= tick()) return PlayerCommands.Refusal.ABILITY_PENDING.ordinal();
    return gate(side, button, dry);
  }

  int gate(int side, int button, boolean dry) {
    CharacterEntity u = s.cmds.championUnit(side, s.buttons[side][button] - 1);
    if (u == null) return spawnedGate(side, button, dry);
    try {
      PlayerCommands.Giving g = dry ? s.cmds.tryAbility(side, u.name()) : s.cmds.useAbility(side, u.name(), "a" + (s.cmdN++));
      if (!dry && g.given()) s.abilityRun[side][button] = g.runTick();
      return g.refusal().ordinal();
    } catch (UnsupportedOperationException e) { return 100; }
  }

  /**
   * A button whose champion no play made (crforge's PlayerCommands names only a play's own units, so it misses the
   * hero Barbarian Barrel's barbarian, which its log spawns): the slot's live copy (ChampionController.champions),
   * tried through crforge's client gates (AbilityCommand.tryGates, package-private: reflection) and given by object id
   * as a replay's command (Standard1v1Battle.useAbility(given, run, side, id, name)), run 20 ticks later.
   * F635b: a crforge build that has PlayerCommands.useAbility(side, objectId, name) / tryAbility(side, objectId)
   * (clashbot fork F635-5) gives it there instead: the same client gates, and its cost promised from the giving to
   * the run, so a play given in those 20 ticks sets it aside. ponytail: on a build without them (the pin) the old
   * path below stays, and the press's cost is not promised while it waits.
   */
  int spawnedGate(int side, int button, boolean dry) {
    CharacterEntity u = null;
    for (CharacterEntity c : s.std.getWorld().kingTower(side).championSlot(s.buttons[side][button]).champions())
      if (!c.isClone()) { u = c; break; }
    if (u == null) return PlayerCommands.Refusal.NO_CHAMPION.ordinal();
    if (promisesById()) {
      try {
        PlayerCommands.Giving g = (PlayerCommands.Giving) (dry ? BY_ID_TRY.invoke(s.cmds, side, u.getId())
            : BY_ID_USE.invoke(s.cmds, side, u.getId(), "a" + (s.cmdN++)));
        if (!dry && g.given()) s.abilityRun[side][button] = g.runTick();
        return g.refusal().ordinal();
      } catch (java.lang.reflect.InvocationTargetException e) {
        if (e.getCause() instanceof UnsupportedOperationException) return 100;
        throw new IllegalStateException(e.getCause());
      } catch (ReflectiveOperationException e) { throw new IllegalStateException(e); }
    }
    int code;
    try {
      if (tryGates == null) {
        var m = AbilityCommand.class.getDeclaredMethod("tryGates", BattleWorld.class, int.class, CharacterEntity.class,
            int.class);
        m.setAccessible(true);
        tryGates = m;
      }
      code = (int) tryGates.invoke(null, s.std.getWorld(), side, u, s.cmds.promised(side));
    } catch (ReflectiveOperationException e) { throw new IllegalStateException(e); }
    if (code != AbilityCommand.OK) return GATE_REFUSAL.getOrDefault(code, PlayerCommands.Refusal.NO_CHAMPION).ordinal();
    if (!dry) {
      int given = Math.max(tick(), 1), run = given + Standard1v1Battle.PLAY_DELAY_TICKS;   // PlayerCommands.stamp
      s.std.useAbility(given, run, side, u.getId(), "a" + (s.cmdN++));
      s.abilityRun[side][button] = run;
    }
    return 0;
  }

  static java.lang.reflect.Method tryGates;
  /** F635b: PlayerCommands' promised by-object-id giving and try (clashbot fork F635-5), or null on a build without. */
  static final java.lang.reflect.Method BY_ID_USE = byId("useAbility", int.class, int.class, String.class);
  static final java.lang.reflect.Method BY_ID_TRY = BY_ID_USE == null ? null : byId("tryAbility", int.class, int.class);
  static java.lang.reflect.Method byId(String name, Class<?>... types) {
    try { return PlayerCommands.class.getMethod(name, types); } catch (NoSuchMethodException e) { return null; }
  }
  /** F635b, for tests: whether this crforge build promises a by-object-id press's cost (BY_ID_USE present). */
  public static boolean promisesById() { return BY_ID_USE != null && BY_ID_TRY != null; }
  /** F635b, for tests: the whole elixir a side's client has promised to its waiting commands (PlayerCommands.promised). */
  public int promised(int side) { return s.cmds.promised(side); }
  /** AbilityCommand gate code -> PlayerCommands.Refusal, as PlayerCommands.abilityRefusal (private) maps it. */
  static final Map<Integer, PlayerCommands.Refusal> GATE_REFUSAL = Map.of(
      AbilityCommand.KING_GONE, PlayerCommands.Refusal.KING_DEAD, AbilityCommand.NO_CHAMPION, PlayerCommands.Refusal.NO_CHAMPION,
      AbilityCommand.COOLDOWN, PlayerCommands.Refusal.COOLDOWN, AbilityCommand.NO_CHARGES, PlayerCommands.Refusal.NO_CHARGES,
      AbilityCommand.NOT_CHAMPION, PlayerCommands.Refusal.NOT_CHAMPION, AbilityCommand.PENDING, PlayerCommands.Refusal.ABILITY_PENDING,
      AbilityCommand.CLONE, PlayerCommands.Refusal.CLONE, AbilityCommand.FROZEN, PlayerCommands.Refusal.FROZEN,
      AbilityCommand.DISABLED, PlayerCommands.Refusal.ABILITY_DISABLED, AbilityCommand.ELIXIR, PlayerCommands.Refusal.NOT_ENOUGH_ELIXIR);

  /**
   * STATUS_HERO as RoyaleSim sets it: a body carrying the ability of one of its side's hero-form slots (not its
   * summons, not a champion). Matched by the slot's ability, as ChampionController.follows does, so a hero body an
   * action spawned (the hero Barbarian Barrel's barbarian) counts too.
   */
  boolean heroBody(CharacterEntity c) {
    var ab = c.getData().ability();
    if (ab == null) return false;
    int side = c.side();
    for (int sl : s.buttons[side]) {
      var slot = s.std.getWorld().kingTower(side).championSlot(sl);
      var champ = slot.getChampion();
      if (s.forms[side][slot.getDeckIndex()] == 2 && champ != null && champ.ability() != null
          && champ.ability().name().equals(ab.name())) return true;
    }
    return false;
  }

  public St save() { return DeepCopy.of(s, this::isShared); }
  public void load(St snap) { s = DeepCopy.of(snap, this::isShared); }
  boolean isShared(Object o) {
    return o instanceof RarityTable || o == spellObj || o == cardNames || shared.contains(o);
  }

  // ---------------------------------------------------------------------------------------------- state
  static int towerSlot(TowerEntity t) {
    if (t.getData().king()) return 0;
    boolean leftEngine = t.x() < 9000;          // Blue's own left is the engine's left; Red's own left the engine's right
    return (t.side() == 0) == leftEngine ? 1 : 2;
  }

  /** packed (cardId << 8 | flags) of a body, or -1 (recorded in missing). */
  int identity(WorldEntity w) {
    String body = w.getData().name(), nm = w.name();
    String root = rootCard(nm);
    bump(stats, "bodies");
    Integer p = byRoot.get(body + "|" + root);
    if (p != null) { bump(stats, "by_root:" + body + "|" + root); return p; }
    p = unique.get(body);
    if (p != null) {
      if (root != null && !root.equals(uniqueCard.get(body))) bump(stats, "root_differs:" + body + "|" + root);
      return p;
    }
    bump(missing, body + "|" + root + "|" + nm.replaceAll("[0-9]+", "#"));
    return -1;
  }

  /**
   * packed (cardId << 4 | motion) of an area effect: a spell object's, else (an evolution's / a troop's area, a spell's
   * second area) the card of the entity that spawned it, as RoyaleSim names such areas, motion AREA; null if none.
   */
  Integer areaCard(AreaEffectEntity a) {
    Integer so = spellObj.get(a.getData().name());
    if (so != null) return so;
    String rec = s.playCard.get(a.name());
    Integer rid = rec == null ? null : cardIndex().get(rec);
    if (rid != null) return rid << 4 | 3;
    Object p = a.getParent();
    if (p instanceof AreaEffectEntity pa) { Integer q = areaCard(pa); return q == null ? null : (q >> 4) << 4 | 3; }
    // a body's or a projectile's area: the card of its root play (the Rage bottle's Rage, a Firecracker's fireworks)
    String card = p instanceof WorldEntity w && !(w instanceof TowerEntity) ? rootCard(w.name())
        : p instanceof ProjectileEntity pp ? s.playCard.get(pp.name()) : null;
    Integer id = card == null ? null : cardIndex().get(card);
    return id == null ? null : id << 4 | 3;
  }

  HashMap<String, Integer> cardIdx;

  HashMap<String, Integer> cardIndex() {
    if (cardIdx == null || cardIdx.size() != cardNames.length) {
      cardIdx = new HashMap<>();
      for (int i = 0; i < cardNames.length; i++) cardIdx.put(cardNames[i], i);
    }
    return cardIdx;
  }

  int cardOf(WorldEntity w) {
    if (w instanceof TowerEntity) return -1;
    int p = identity(w);
    return p < 0 ? -2 : p >> 8;
  }

  static synchronized int typeOf(String body) {
    Integer t = unitType.get(body);
    if (t == null) { t = unitType.size(); unitType.put(body, t); }
    return t;
  }

  public static synchronized String[] unitTypes() { return unitType.keySet().toArray(new String[0]); }

  /**
   * unitTypes() after giving every alive body's row its id: a body first seen since the last state() has none yet, and
   * sim_unit_state.extract reads the names BEFORE state_json (an index past the list's end otherwise).
   */
  public String[] unitTypesNow() {
    if (s != null)
      for (BattleEntity e : s.std.getBattle().getHolder().entities())
        if (e instanceof WorldEntity w && w.getView().isAlive()) typeOf(w.getData().name());
    return unitTypes();
  }

  static void str(StringBuilder b, String v) {
    b.append('"');
    for (int i = 0; i < v.length(); i++) { char c = v.charAt(i); if (c == '"' || c == '\\') b.append('\\'); b.append(c); }
    b.append('"');
  }

  static void ints(StringBuilder b, int... v) {
    b.append('[');
    for (int i = 0; i < v.length; i++) { if (i > 0) b.append(','); b.append(v[i]); }
    b.append(']');
  }

  // ---------------------------------------------------------------------------------------------- cue values (F1c-2)
  // Each value below is read from crforge's own view / targeting / buff / movement state and put in RoyaleSim's
  // encoding; F1c-2 measures each against RoyaleSim fin16 on matched scenarios (facade/cues/cue_ab.py -> results/f1c2).

  /**
   * The reference as RoyaleSim's target: crforge also holds the DEFAULT target (the tower a unit walks at, a tower's
   * fallback) as its reference while nothing is in sight; RoyaleSim holds none then. Kept: any reference while the
   * owner attacks, else one inside crforge's own selection reach (CandidateSelector: the target's radius + the sight
   * range + the owner's radius, + the crown-tower / building extra); else none.
   */
  static TargetView acquired(WorldEntity w) {
    TargetingState t = w.getTargeting();
    TargetView ref = t.getReference();
    if (ref == null || w.getView().getState() == GridEntityState.ATTACKING) return ref;
    long reach = ref.radius() + SightRange.sightRange(t)
        + (PathfindingGlobals.ADD_CHARACTER_RANGE_TO_RADIUS ? t.getConfig().collisionRadius() : 0)
        + (ref.crownTower() ? PathfindingGlobals.EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS
            : ref.building() ? PathfindingGlobals.EXTRA_SIGHT_RANGE_TO_BUILDING : 0);
    long dx = ref.x() - w.x(), dy = ref.y() - w.y();
    return dx * dx + dy * dy <= reach * reach ? ref : null;
  }

  /**
   * RoyaleSim attack phase from crforge's attacking state: 0 Idle (not attacking), 2 Cooldown (attacking with the attack
   * timer standing on a hit-speed multiple: the tick a hit lands, and the hold after it while the target is gone), else
   * 1 Windup. Traced tick by tick (trace.py) on a Tesla and a princess tower against a Knight: the same ticks in both
   * engines. crforge's hitInProgress is not used: it also drops the tick after a ranged hit, where RoyaleSim is in Windup.
   */
  static int phase(WorldEntity w) {
    if (w.getView().getState() != GridEntityState.ATTACKING) return 0;
    int at = w.getTargeting().getAttackTimerMs(), hs = w.getData().hitSpeedMs();
    return at > 0 && hs > 0 && at % hs == 0 ? 2 : 1;
  }

  /** RoyaleSim's one stun flag in ticks: the longest buff with speed or hit speed -100 (Freeze, Zap, stun buffs). */
  static int stunTicks(WorldEntity w) {
    int ms = 0;
    for (BuffInstance bi : w.getBuffs().items()) {
      BuffData d = bi.getBuff();
      if (d.speedMultiplier() <= -100 || d.hitSpeedMultiplier() <= -100) ms = Math.max(ms, bi.getRemaining());
    }
    return (ms + 49) / 50;
  }

  /** crforge charge progress (0..10000, -1 none) as RoyaleSim's charge (0..1000; 1000 once charged). */
  static int charge(WorldEntity w) {
    if (!(w instanceof CharacterEntity c)) return 0;
    GridEntity v = w.getView();
    if ((v.getFlags() & v.getFlagBits().charging()) != 0) return 1000;
    int p = c.getUnit().movement().getChargeProgress();
    return p <= 0 ? 0 : Math.min(1000, p / 10);
  }

  /**
   * A pushback in flight as RoyaleSim's knockback ticks: its budget drops 25 per visit (MovementState.pushbackBudget),
   * RoyaleSim counts the visit that ends it too (traced: budget 200 -> 9, 175 -> 8 ... a Firecracker's recoil).
   */
  static int knockTicks(WorldEntity w) {
    if (!(w instanceof CharacterEntity c)) return 0;
    var mv = c.getUnit().movement();
    return mv.getPushbackInFlight() == 1 ? mv.getPushbackBudget() / 25 + 1 : 0;
  }

  /**
   * Tesla-type hide cue: RoyaleSim reads Hidden from the first tick the hide counter leaves 0 going down until it rises
   * (crforge 0 < counter <= hide time), and Up while it comes back up attacking (counter past the hide time, or turned
   * back below 0) and while up (traced). RoyaleSim's rare Rising has no crforge state found to match.
   */
  static String hide(WorldEntity w) {
    if (!(w instanceof CharacterEntity c) || !w.getData().hidesWhenNotAttacking()) return "Up";
    int k = c.getUnit().timers().getHideCounterMs(), h = w.getData().hideTimeMs();
    return k > 0 && k <= h ? "Hidden" : "Up";
  }

  /** RoyaleSim's footprint [x0, y0, x1, y1] (subtiles) of a tower or building: crforge's placement footprint in tiles. */
  static String footprint(WorldEntity w) {
    if (!(w instanceof TowerEntity) && !w.getData().building()) return "null";
    int half = PlacementSearch.footprint(w.getData()) * 500;
    return "[" + (w.x() - half) * K + "," + (w.y() - half) * K + "," + (w.x() + half) * K + "," + (w.y() + half) * K + "]";
  }

  /**
   * STATUS_ABILITY_WINDUP (64) / STATUS_ABILITY_ACTIVE (128) from the champion / hero body's view state, as fin16 sets
   * them (traced on the hero Knight and the Monk, trace.py --press): casting = 64, plus 128 once its warning has run
   * out; the ability's follow-up = 64 | 128. An ability crforge runs without a cast state (hero Ice Wizard, hero
   * Valkyrie: the body keeps walking / attacking) has no crforge view state to read: no bit (fin16 sets 128 there).
   */
  static int abilityBits(WorldEntity w) {
    if (!(w instanceof CharacterEntity c)) return 0;
    int st = w.getView().getState();
    if (st == GridEntityState.CASTING) return c.getUnit().timers().getAbilityWarningCountdown() >= 1 ? 64 : 64 | 128;
    return st == GridEntityState.ABILITY_FOLLOW_UP ? 64 | 128 : 0;
  }

  /** STATUS_EVOLVED (8): the body runs an evolution row of crforge's tables (Knight_EV1, AngryBarbarian_EV1_2 ...). */
  static int evolvedBit(WorldEntity w) {
    return w instanceof TowerEntity || !w.getData().name().toUpperCase().contains("_EV") ? 0 : 8;   // electro_dragon_ev1
  }

  /**
   * The Mighty Miner's dropped bomb. crforge: a 0-hp building body counting its deploy down (+30 .. +50 after the
   * press), then a blast area for one tick. fin16: a FLIGHT spell row of the Mighty Miner card at the bomb, delay = the
   * countdown in ticks, and no area (traced tick by tick, cues/mm_bomb.py). The facade reports it the fin16 way: the
   * body as that row, its MightyMinerExplosion area (source null in crforge) dropped.
   * ponytail: this one row by name; other 0-hp bombs (Giant Skeleton's, the Balloon's) were not traced.
   */
  /** The bomb's blast (crforge names its source null; the row is the bomb's alone). */
  static boolean bombBlast(AreaEffectEntity a) { return a.getData().name().equals("MightyMinerExplosion"); }

  static boolean bombAsSpell(Object o) {
    return o instanceof WorldEntity w && w.getData().name().equals("MightyMinerBomb");
  }

  static final String[] PHASES = {"\"Idle\"", "\"Windup\"", "\"Cooldown\""};

  /**
   * The part of RoyaleSim's Battle.save() JSON that pipeline/sim_unit_state.extract reads, entity rows in state()'s
   * order (all alive), from crforge's own state (the helpers above): attack / load timers, acquired-target phase,
   * river jump and dash (the view's state), base walk speed, the hide counter, the charge flag; shots carry their
   * firer (the index of its row here), their target buff's time at their level and their damage.
   */
  public String cueSave() {
    StringBuilder a = new StringBuilder(), pos = new StringBuilder(), at = new StringBuilder(), ld = new StringBuilder(),
        kind = new StringBuilder(), ph = new StringBuilder(), sp = new StringBuilder(), ch = new StringBuilder(),
        jp = new StringBuilder(), ds = new StringBuilder(), hd = new StringBuilder();
    StringBuilder spells = new StringBuilder(), shots = new StringBuilder();
    String[] motions = {"Flight", "Airborne", "Rolling", "Area", "Pulsing", "Fuse", "Strikes", "Scheduled"};
    HashMap<Integer, Integer> row = new HashMap<>();      // entity id -> its row index (a shot's firer ref)
    for (BattleEntity e : s.std.getBattle().getHolder().entities())
      if (e instanceof WorldEntity w && w.getView().isAlive() && !bombAsSpell(w)) row.put(w.getId(), row.size());
    int n = 0;
    for (BattleEntity e : s.std.getBattle().getHolder().entities()) {
      if (e instanceof WorldEntity w) {
        GridEntity v = w.getView();
        if (!v.isAlive()) continue;
        if (bombAsSpell(w)) {
          if (cardIndex().get(rootCard(w.name())) == null) continue;
          if (spells.length() > 0) spells.append(',');
          spells.append("{\"motion\":{\"Flight\":{\"pos\":{\"x\":").append(w.x() * K).append(",\"y\":")
              .append(w.y() * K).append("}}}}");
          continue;
        }
        String sep = n++ > 0 ? "," : "";
        var tg = w.getTargeting();
        a.append(sep).append("true");
        pos.append(sep).append("{\"x\":").append(w.x() * K).append(",\"y\":").append(w.y() * K).append('}');
        at.append(sep).append(tg.getAttackTimerMs());
        ld.append(sep).append(tg.getLoadTimerMs());
        kind.append(sep).append(w instanceof TowerEntity t ? (t.getData().king() ? "\"KingTower\"" : "\"PrincessTower\"")
            : w.getData().building() ? "\"Building\"" : "\"Troop\"");
        ph.append(sep).append(PHASES[phase(w)]);
        sp.append(sep).append(w instanceof CharacterEntity && !w.getData().building() ? w.getData().speed() * K : 0);
        ch.append(sep).append((v.getFlags() & v.getFlagBits().charging()) != 0);
        jp.append(sep).append(v.getState() == GridEntityState.JUMPING);
        ds.append(sep).append(v.getState() == GridEntityState.DASHING ? "\"Dashing\"" : "\"None\"");
        hd.append(sep).append('"').append(hide(w)).append('"');
      } else if (e instanceof ProjectileEntity p) {
        Integer so = spellObj.get(p.getData().name());
        if (so != null) {
          if (spells.length() > 0) spells.append(',');
          spells.append("{\"motion\":{\"").append(motions[so & 15]).append("\":{\"pos\":{\"x\":").append(p.getX() * K)
              .append(",\"y\":").append(p.getY() * K).append("}}}}");
        } else {
          if (shots.length() > 0) shots.append(',');
          WorldEntity o = p.getOwner() != null ? p.getOwner() : p.getRoot();   // a spark / split shot: its root body
          Integer fi = o == null ? null : row.get(o.getId());
          String buff = p.getData().targetBuff();
          shots.append("{\"firer\":").append(fi == null ? "null" : "{\"index\":" + fi + ",\"generation\":0}")
              .append(",\"buff\":");
          if (buff == null) shots.append("null");
          else {
            shots.append("{\"buff\":");
            str(shots, buff);
            shots.append(",\"time_ms\":").append(p.getData().buffTime(p.getPackedLevel())).append('}');
          }
          shots.append(",\"damage\":").append(p.damage()).append('}');
        }
      } else if (e instanceof AreaEffectEntity ae) {
        Integer so = areaCard(ae);
        if (so == null || bombBlast(ae)) continue;
        int motion = so & 15;
        // an area a troop / evolution / spell's second object makes: Pulsing when it hits every HitSpeed, as spell_objects
        if (motion == 3 && !spellObj.containsKey(ae.getData().name()) && ae.getData().hitSpeedMs() > 0) motion = 4;
        // an area riding on a body (the Ice Wizard's aura ...): fin16's save calls it Attached (no state_json code)
        String mname = ae.getFollow() != null || ae.getData().followsParent() ? "Attached" : motions[motion];
        if (spells.length() > 0) spells.append(',');
        spells.append("{\"motion\":{\"").append(mname).append("\":{\"pos\":{\"x\":").append(ae.x() * K)
            .append(",\"y\":").append(ae.y() * K).append("},\"life_ms\":").append(Math.max(0, ae.getCountdown()))
            .append("}}}");
      }
    }
    String zeros = n == 0 ? "" : "0" + ",0".repeat(n - 1);
    return "{\"ents\":{\"alive\":[" + a + "],\"pos\":[" + pos + "],\"attack_ms\":[" + at + "],\"attack_load_ms\":[" + ld
        + "],\"jumping\":[" + jp + "],\"dash_state\":[" + ds + "],\"attack_phase\":[" + ph + "],\"kind\":[" + kind
        + "],\"speed\":[" + sp + "],\"hide\":[" + hd + "],\"charged\":[" + ch + "],\"generation\":[" + zeros
        + "]},\"projectiles\":[" + shots + "],\"spells\":[" + spells + "]}";
  }

  public String state() {
    Standard1v1Battle std = s.std;
    LadderMatch m = std.getMatch();
    BattleWorld world = std.getWorld();
    int tick = tick();
    boolean over = over();
    StringBuilder b = new StringBuilder(8192);
    int full = m.getTimeline().getFullBarMs();
    b.append("{\"tick\":").append(tick).append(",\"tick_ms\":50,\"regular_ticks\":3600,\"overtime_ticks\":2400")
        .append(",\"elixir_rate\":").append(full > 0 ? Math.round(2800f / full) : 1)
        .append(",\"overtime\":").append(m.getTimeline().overtime())
        .append(",\"game_over\":").append(over)
        .append(",\"winner\":").append(!over ? -1 : m.getWinner() < 0 ? 2 : m.getWinner());
    int[][] towerHp = new int[2][3];
    boolean[] kingActive = new boolean[2];
    StringBuilder ents = new StringBuilder(4096), spells = new StringBuilder(), shots = new StringBuilder();
    List<BattleEntity> list = std.getBattle().getHolder().entities();
    HashMap<Integer, Integer> mount = new HashMap<>();     // rider id -> the id of the body it rides (Ram Rider ...)
    for (BattleEntity e : list)
      if (e instanceof CharacterEntity c) for (CharacterEntity r : c.riders()) mount.put(r.getId(), c.getId());
    for (BattleEntity e : list) {
      if (e instanceof WorldEntity w) {
        GridEntity v = w.getView();
        if (!v.isAlive()) continue;
        if (bombAsSpell(w)) {                     // the fin16 row: [team, card, FLIGHT, at, aim = at, delay ticks, ...]
          Integer cid = cardIndex().get(rootCard(w.name()));
          if (cid == null) continue;
          if (spells.length() > 0) spells.append(',');
          ints(spells, w.side(), cid, 0, w.x() * K, w.y() * K, w.x() * K, w.y() * K, (v.getDeployCountdown() + 49) / 50,
              0, 0, 0, 0);
          continue;
        }
        HitPoints h = w.getHitPoints();
        int hp = h == null ? 0 : h.getHitPoints(), mhp = h == null ? 0 : h.getMaximum();
        int kind, card = -1, slot = -1, flags = 0;
        if (w instanceof TowerEntity t) {
          kind = t.getData().king() ? 2 : 3;
          slot = towerSlot(t);
          towerHp[t.side()][slot] = Math.max(hp, 0);
          if (slot == 0) kingActive[t.side()] = !t.isInactive();
        } else {
          kind = w.getData().building() ? 1 : 0;
          int p = identity(w);
          if (p >= 0) { card = p >> 8; flags = p & 0xff; }
          if (w instanceof CharacterEntity c) {
            flags |= (c.underground() ? 1 : 0) | (c.invisible() ? 2 : 0) | (c.hidden() ? 4 : 0);
            // STATUS_HERO as RoyaleSim sets it: the body that carries a hero-form card's ability (not its summons,
            // not a champion)
            if (heroBody(c)) flags |= 16;
          }
        }
        if ((v.getFlags() & v.getFlagBits().charging()) != 0) flags |= 256;          // STATUS charged
        if (hide(w).equals("Hidden")) flags |= 4;                                   // STATUS hidden, as the hide cue
        flags |= abilityBits(w) | evolvedBit(w);                                    // STATUS ability_* / evolved
        int target = -1;
        TargetView ref = acquired(w);
        if (ref != null) { WorldEntity te = world.entityOf(ref.getEntity()); if (te != null) target = te.getId(); }
        int deployMs = w instanceof CharacterEntity ? v.getDeployCountdown() : 0;
        if (ents.length() > 0) ents.append(',');
        ents.append('[').append(w.getId()).append(',').append(w.side()).append(',').append(kind).append(',').append(card)
            .append(',').append(slot).append(',').append(w.x() * K).append(',').append(w.y() * K).append(',').append(hp)
            .append(',').append(mhp).append(',').append(v.getCollisionRadius() * K).append(',').append(w.getData().air())
            .append(',').append((deployMs + 49) / 50).append(',').append(stunTicks(w)).append(',').append(knockTicks(w))
            .append(',').append(footprint(w)).append(',').append(target).append(',').append(phase(w)).append(',');
        ints(ents, v.getDirX(), v.getDirY());
        ents.append(',').append(h == null ? 0 : h.getShield()).append(",[");
        LinkedHashMap<String, Integer> buffs = new LinkedHashMap<>();   // RoyaleSim lists a buff once: its longest time
        String idle = w.getData().buffWhenNotAttacking();   // fin16 applies it implicitly, lists no buff for it
        for (BuffInstance bi : w.getBuffs().items())        // FOREVER (-1): RoyaleSim's owner-lifetime sentinel
          if (!bi.getBuff().name().equals(idle))
            buffs.merge(bi.getBuff().name(), bi.getRemaining() == BuffInstance.FOREVER ? 999999 : bi.getRemaining(), Math::max);
        boolean first = true;
        for (Map.Entry<String, Integer> bf : buffs.entrySet()) {
          if (!first) ents.append(',');
          first = false;
          ents.append('[');
          str(ents, bf.getKey());
          ents.append(',').append(bf.getValue()).append(']');
        }
        // ability ticks: fin16 counts the follow-up only, one more than crforge's countdown (traced on the Monk)
        int ability = w instanceof CharacterEntity c && v.getState() == GridEntityState.ABILITY_FOLLOW_UP
            ? c.getUnit().timers().getAbilityCountdown() + 1 : 0;
        int[] dest = {-1, -1};                     // an explicit move destination (a tunnel / dig / ability point)
        if (w instanceof CharacterEntity c && c.getUnit().movement().getExplicitX() >= 0)
          dest = new int[] {c.getUnit().movement().getExplicitX() * K, c.getUnit().movement().getExplicitY() * K};
        ents.append("],").append(flags).append(',').append(w.level()).append(',').append(mount.getOrDefault(w.getId(), -1))
            .append(',').append(charge(w)).append(',').append(dest[0]).append(',').append(dest[1]).append(',')
            .append(Math.max(0, ability)).append(',')
            .append(typeOf(w.getData().name())).append(']');
      } else if (e instanceof ProjectileEntity p) {
        Integer so = spellObj.get(p.getData().name());
        if (so != null) {
          if (spells.length() > 0) spells.append(',');
          ints(spells, p.getSide(), so >> 4, so & 15, p.getX() * K, p.getY() * K, p.getAimX() * K, p.getAimY() * K,
              Math.max(0, p.getDelayMs()) / 50, 0, 0, 0, -1);
        } else {
          WorldEntity owner = p.getOwner(), tgt = p.getTarget();
          int firer = owner == null ? -2 : cardOf(owner);
          if (shots.length() > 0) shots.append(',');
          ints(shots, p.getSide(), p.getX() * K, p.getY() * K, p.getAimX() * K, p.getAimY() * K,
              tgt == null || !tgt.getView().isAlive() ? -1 : tgt.getId(), 0, firer);
        }
      } else if (e instanceof AreaEffectEntity a) {
        if (bombBlast(a)) continue;               // the bomb's blast: fin16 has no area for it
        Integer so = areaCard(a);
        if (so == null) { bump(missing, "area:" + a.getData().name() + "|" + a.name().replaceAll("[0-9]+", "#")); continue; }
        int motion = so & 15;
        if (spells.length() > 0) spells.append(',');
        ints(spells, a.side(), so >> 4, motion, a.x() * K, a.y() * K, a.x() * K, a.y() * K,
            motion == 4 ? Math.max(0, a.getCountdown()) / 50 : 0, 0, 0, 0, -1);
      }
    }
    b.append(",\"players\":[");
    for (int side = 0; side < 2; side++) {
      MatchSide ms = m.side(side);
      int[] h = ms.getHand().slots();
      List<Integer> q = ms.getHand().queue();
      if (side > 0) b.append(',');
      b.append("{\"team\":").append(side).append(",\"elixir_milli\":").append(ms.getElixir() / 10).append(",\"hand\":");
      int[] hand = new int[4];
      for (int k = 0; k < 4; k++) hand[k] = h[k] >= 0 ? s.deckIds[side][h[k]] : -1;
      ints(b, hand);
      b.append(",\"next_card\":").append(q.isEmpty() ? -1 : s.deckIds[side][q.get(0)])
          .append(",\"crowns\":").append(m.crowns(side)).append(",\"tower_hp\":");
      ints(b, towerHp[side]);
      b.append(",\"tower_max_hp\":");
      ints(b, s.towerMax[side]);
      b.append(",\"king_active\":").append(kingActive[side]).append(",\"abilities\":[");
      // one row per button from the deal on, as RoyaleSim: [available (the press would be taken but for the elixir),
      // spent (no charge left), the ability's cost, the button's card, its cooldown ticks left]
      TowerEntity king = world.kingTower(side);
      for (int button = 0; button < s.buttons[side].length; button++) {
        var slot = king.championSlot(s.buttons[side][button]);
        int code = gate(side, button, true);    // fin16 keeps available 1 while a press waits
        if (button > 0) b.append(',');
        ints(b, code == 0 || code == PlayerCommands.Refusal.NOT_ENOUGH_ELIXIR.ordinal() ? 1 : 0,
            slot.getCharges() == 0 ? 1 : 0, slot.getChampion().ability() == null ? 0 : slot.getChampion().ability().manaCost(),
            s.deckIds[side][slot.getDeckIndex()], (slot.getCooldownMs() + 49) / 50);
      }
      // RoyaleSim's evo rows: [card id, plays since its last evolved play, 1 if its next play is evolved, plays needed]
      // per evolution-slot card in deck order (MatchSide.item: the item a play given now carries)
      b.append("],\"evo\":[");
      boolean firstEvo = true;
      for (int idx = 0; idx < 8; idx++) {
        if ((ms.slotFlags(idx) & MatchSide.EVOLUTION_SLOT) == 0) continue;
        var evoRow = ms.deck().get(idx).formRow(org.crforge.core.battle.match.MatchCard.EVO_FORM);
        if (!firstEvo) b.append(',');
        firstEvo = false;
        ints(b, s.deckIds[side][idx], ms.evolutionCount(idx),
            ms.item(idx).field() == org.crforge.core.battle.match.EvolutionItem.EVOLVED ? 1 : 0, evoRow.darkElixirCost());
      }
      b.append("],\"pending_cost\":").append(s.cmds.promised(side) / 10).append(",\"deck\":");
      ints(b, s.deckIds[side]);
      b.append(",\"forms\":");
      ints(b, s.forms[side]);
      b.append('}');
    }
    b.append("],\"entities\":[").append(ents).append("],\"spells\":[").append(spells).append("],\"projectiles\":[")
        .append(shots).append("]}");
    return b.toString();
  }
}
