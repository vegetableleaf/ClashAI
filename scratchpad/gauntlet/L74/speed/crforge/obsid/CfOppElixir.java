// S3b-3c (plan1026 Pillar 4): production's PUBLIC opponent-elixir estimate (the GenModel row's sc[5] at feature
// version >= 4) on the facade battle, for one seat. A port of pipeline/public_observation.PublicObserver.update
// (source 'sim') + opp_elixir_count.PlayDetector.feed + OppElixirCounter, as e1_eval.Match.prepare runs them: fed the
// board at that seat's own decision ticks only, read as estimate_at(tick + h). It never reads either side's elixir,
// hand or deck: only bodies (alive, a card, the opponent's) and the board's spell objects.
//
// The frame is what RoyaleSelfPlayEnv.raw() + public_frame(source='sim') give: a body is the facade's state() body
// (alive, not a tower, card from the identity tables, hp > 0 or max_hp <= 0) and its detector key is filled from
// Python on first sight ("card|body row|form" -> public card id -> vocab key, by public_frame on that raw entity);
// a spell object is a state() spell (a spell-object projectile / an area with a card) or a shot (its firer's card),
// kept when its card's key is a cards.yaml 'spell' (Python fills the card id -> key table).

import java.nio.FloatBuffer;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.battle.projectile.ProjectileEntity;
import org.crforge.core.pathfinding.combat.HitPoints;

public final class CfOppElixir {
  /** The detector key tables, shared by every match (Python fills them). A key is an index into name / cost / window. */
  public static final class Keys {
    final HashMap<String, Integer> body = new HashMap<>();      // "card|body row|form" -> key << 2 | catalog form, -1 = none
    public int[] spell = new int[0];                            // card id + 2 -> key if its objects are spells, else -1
    public boolean shots;                                       // raw() carries projectiles (env feature_version >= 4)
    final ArrayList<String> name = new ArrayList<>();
    final ArrayList<Double> cost = new ArrayList<>();           // NaN = card_cost None (nothing charged)
    final ArrayList<Integer> window = new ArrayList<>();        // swarm_ticks_by_key.get(key, swarm_ticks)
    final ArrayList<Integer> gid = new ArrayList<>();           // the policy's gid.get(card_key(key), 0) (opp_past)
    public final Set<String> missing = java.util.concurrent.ConcurrentHashMap.newKeySet();   // S3b-4: CfLoop pool threads add; "card|body row|form#entity id" seen, not in body

    public int addKey(String n, double c, int w, int g) {
      name.add(n); cost.add(c); window.add(w); gid.add(g);
      return name.size() - 1;
    }
    public void putBody(String k, int key, int form) { body.put(k, key < 0 ? -1 : key << 2 | form); }
    public String[] takeMissing() { String[] a = missing.toArray(new String[0]); missing.clear(); return a; }
  }

  static final double START = 6.0, MAX = 10.0, DEATH_RADIUS = 1500.0;
  static final int PARENT_MEMORY = 60, SPELL_GAP = 100;

  static final class Body {
    final int key, form, mhp;                                   // form: catalog_card_form of its public card id
    final double x, y;
    int gone = -1;                                              // tick of the first frame without it; -1 = on board
    Body(int key, int form, int mhp, double x, double y) { this.key = key; this.form = form; this.mhp = mhp; this.x = x; this.y = y; }
  }

  final CfObsBind.FacadeMatch m;
  final int seat;
  final Keys keys;
  // PlayDetector
  final HashSet<Integer> seen = new HashSet<>();
  final HashMap<Integer, Integer> open = new HashMap<>();       // key -> tick of its latest charged play
  final HashMap<Integer, Body> recent = new HashMap<>();        // entity id -> body (+ gone tick)
  final HashMap<Integer, Integer> playHp = new HashMap<>();     // key -> strongest max_hp a charged group showed
  public int spawns;
  /** How often each rule decided something, over every detector of this JVM (diagnostics: which edge cases the
   *  identity run exercised). Index = EDGE_NAMES. */
  public static final String[] EDGE_NAMES = {"swarm_join", "spawn_parent", "spawn_death", "spawn_both",
      "body_play_spell_visible", "spell_new_sighting", "spell_still_visible", "window_skip", "spell_body_skip",
      "play_body", "play_spell", "play_no_cost", "rebase"};
  public static final long[] EDGE = new long[EDGE_NAMES.length];
  // PublicObserver
  final HashMap<Integer, Integer> spellLastSeen = new HashMap<>(), lastPlay = new HashMap<>();
  public int plays;
  // OppElixirCounter
  int ctick;
  double est;
  int[] ticks = new int[64], pkey = new int[64], pform = new int[64];
  double[] ests = new double[64], px = new double[64], py = new double[64];   // the plays (PublicObserver.plays)
  int n, viewTick;
  // frame scratch
  final LinkedHashMap<Integer, Body> cur = new LinkedHashMap<>();
  final LinkedHashMap<Integer, double[]> spells = new LinkedHashMap<>();   // key -> {sum x, sum y, objects}

  public CfOppElixir(CfObsBind.FacadeMatch m, int seat, Keys keys) { this.m = m; this.seat = seat; this.keys = keys; reset(); }

  public void reset() {
    seen.clear(); open.clear(); recent.clear(); playHp.clear(); spellLastSeen.clear(); lastPlay.clear();
    spawns = plays = n = 0;
    ctick = 0;
    est = START;
  }

  /** public_frame (source 'sim') of the facade battle, opponent side only. false = a body key is missing (keys.missing:
   *  Python fills it, then calls again); nothing changes until a frame is complete. */
  boolean frame() {
    cur.clear();
    spells.clear();
    boolean ok = true;
    CfCore core = m.core;
    for (BattleEntity e : m.std.getBattle().getHolder().entities()) {
      if (e instanceof WorldEntity w) {
        if (w instanceof TowerEntity || !w.getView().isAlive() || w.side() == seat) continue;
        HitPoints h = w.getHitPoints();
        int hp = h == null ? 0 : h.getHitPoints(), mhp = h == null ? 0 : h.getMaximum();
        if (hp <= 0 && mhp > 0) continue;
        String body = w.getData().name(), root = core.rootCard(w.name());
        Integer p = m.packed(body, root);
        if (p == null) continue;                                   // card -1: raw() drops it
        int flags = p & 0xff;
        if (w instanceof CharacterEntity c && m.hero(c, root)) flags |= 16;
        int form = (flags & 16) != 0 ? 2 : (flags & 8) != 0 ? 1 : 0;   // obs_contract.entity_form
        String k = (p >> 8) + "|" + body + "|" + form;
        Integer v = keys.body.get(k);
        if (v == null) { keys.missing.add(k + "#" + w.getId()); ok = false; continue; }
        if (v >= 0) cur.put(w.getId(), new Body(v >> 2, v & 3, mhp, w.x(), w.y()));
      } else if (e instanceof ProjectileEntity p) {
        Integer so = core.spellObj.get(p.getData().name());
        int card;
        if (so != null) card = so >> 4;
        else if (!keys.shots) continue;
        else {
          WorldEntity o = p.getOwner();
          Integer q = o == null || o instanceof TowerEntity ? null : m.packed(o.getData().name(), core.rootCard(o.name()));
          card = o instanceof TowerEntity ? -1 : q == null ? -2 : q >> 8;   // CfCore.state()'s firer
        }
        spell(p.getSide(), card, p.getX(), p.getY());
      } else if (e instanceof AreaEffectEntity a) {
        Integer so = core.areaCard(a);
        if (so != null) spell(a.side(), so >> 4, a.x(), a.y());
      }
    }
    return ok;
  }

  void spell(int side, int card, int x, int y) {
    if (side == seat || side < 0 || side > 1) return;
    if (card + 2 >= keys.spell.length) throw new IllegalStateException("spell table has no card " + card);
    int key = keys.spell[card + 2];
    if (key >= 0) {
      double[] g = spells.computeIfAbsent(key, z -> new double[3]);
      g[0] += x; g[1] += y; g[2]++;
    }
  }

  /** PublicObserver.update at this seat's decision (tick = the battle's). false = keys missing, nothing fed. */
  public boolean update() {
    if (!frame()) return false;
    final int tick = m.tick();
    // ---- PlayDetector.feed
    LinkedHashMap<Integer, ArrayList<Integer>> groups = new LinkedHashMap<>();   // key -> new entity ids
    for (Map.Entry<Integer, Body> c : cur.entrySet())
      if (seen.add(c.getKey())) groups.computeIfAbsent(c.getValue().key, x -> new ArrayList<>()).add(c.getKey());
    for (Iterator<Map.Entry<Integer, Body>> it = recent.entrySet().iterator(); it.hasNext(); ) {
      Map.Entry<Integer, Body> r = it.next();
      if (cur.containsKey(r.getKey())) continue;                  // replaced below
      Body b = r.getValue();
      if (b.gone < 0) b.gone = tick;
      if (tick - b.gone > PARENT_MEMORY) it.remove();
    }
    recent.putAll(cur);
    LinkedHashMap<Integer, double[]> events = new LinkedHashMap<>();   // key -> {form, x, y} of the play
    for (Map.Entry<Integer, ArrayList<Integer>> g : groups.entrySet()) {
      int key = g.getKey();
      ArrayList<Integer> group = g.getValue();
      Integer op = open.get(key);
      if (op != null && tick - op <= keys.window.get(key)) { EDGE[0]++; continue; }   // same cast: swarm body
      boolean inf = true;
      int mx = 0;
      for (int id : group) { int h = cur.get(id).mhp; if (h > 0) { mx = inf ? h : Math.max(mx, h); inf = false; } }
      int ph = playHp.getOrDefault(key, 0);
      boolean parent = false, death = false;
      for (Map.Entry<Integer, Body> r : recent.entrySet()) {
        Body b = r.getValue();
        if (b.key != key) continue;
        if (!group.contains(r.getKey())
            && ((!inf && b.mhp > mx) || (b.mhp <= 0 && !inf && mx < ph))) parent = true;
        if (!cur.containsKey(r.getKey()) && b.mhp > 0 && (inf || b.mhp < mx))
          for (int id : group) {
            Body c = cur.get(id);
            double dx = b.x - c.x, dy = b.y - c.y;
            if (dx * dx + dy * dy <= DEATH_RADIUS * DEATH_RADIUS) { death = true; break; }
          }
      }
      if (parent || death) { spawns += group.size(); EDGE[parent && death ? 3 : parent ? 1 : 2]++; continue; }
      open.put(key, tick);
      if (!inf) playHp.put(key, Math.max(ph, mx));
      double[] ev = new double[3];                                 // max form, birth centroid
      for (int id : group) { Body c = cur.get(id); ev[0] = Math.max(ev[0], c.form); ev[1] += c.x; ev[2] += c.y; }
      ev[1] /= group.size(); ev[2] /= group.size();
      events.put(key, ev);
    }
    // ---- PublicObserver.update: body plays, then spell presence, charged in key order
    TreeMap<Integer, double[]> cand = new TreeMap<>(Comparator.comparing(keys.name::get));
    for (Map.Entry<Integer, double[]> ev : events.entrySet()) {
      Integer s = spellLastSeen.get(ev.getKey());
      if (s == null || tick - s > SPELL_GAP) cand.put(ev.getKey(), ev.getValue()); else EDGE[4]++;
    }
    for (Map.Entry<Integer, double[]> sp : spells.entrySet()) {
      int key = sp.getKey();
      double[] g = sp.getValue();
      Integer prev = spellLastSeen.put(key, tick);
      if (prev == null || tick - prev > SPELL_GAP) {               // the spell's sighting replaces a body's (form 0)
        cand.put(key, new double[] {0, g[0] / g[2], g[1] / g[2]});
        EDGE[5]++;
      } else EDGE[6]++;
    }
    for (Map.Entry<Integer, double[]> c : cand.entrySet()) {
      int key = c.getKey();
      Integer lp = lastPlay.get(key);
      if (lp != null && tick - lp <= keys.window.get(key)) { EDGE[7]++; continue; }
      Integer s = spellLastSeen.get(key);
      if (!spells.containsKey(key) && s != null && tick - s <= SPELL_GAP) { EDGE[8]++; continue; }
      EDGE[spells.containsKey(key) ? 10 : 9]++;
      lastPlay.put(key, tick);
      play(tick, key, c.getValue());
    }
    return true;
  }

  // ---- OppElixirCounter (START 6.0, cap 10, the facade's regen schedule = REGEN_SCHEDULE) + estimate_at
  void play(int tick, int key, double[] ev) {
    double cost = keys.cost.get(key);
    if (tick > ctick) { est = Math.min(MAX, est + m.regen(ctick, tick)); ctick = tick; }
    if (Double.isNaN(cost)) EDGE[11]++;
    else {
      if (est < cost) { est = cost; EDGE[12]++; }                                  // re-base: the estimate was low
      est -= cost;
    }
    if (n == ticks.length) {
      ticks = Arrays.copyOf(ticks, 2 * n); ests = Arrays.copyOf(ests, 2 * n); pkey = Arrays.copyOf(pkey, 2 * n);
      pform = Arrays.copyOf(pform, 2 * n); px = Arrays.copyOf(px, 2 * n); py = Arrays.copyOf(py, 2 * n);
    }
    ticks[n] = tick; pkey[n] = key; pform[n] = (int) ev[0]; px[n] = ev[1]; py[n] = ev[2];
    ests[n++] = est;
    plays++;
  }

  /** estimate_at(t): the counter after the last play seen strictly before t, regenerated to t. */
  public double estimateAt(int t) {
    viewTick = t;
    int i = n - 1;
    while (i >= 0 && ticks[i] >= t) i--;
    int t0 = i >= 0 ? ticks[i] : 0;
    double e = i >= 0 ? ests[i] : START;
    return t > t0 ? Math.min(MAX, e + m.regen(t0, t)) : e;
  }

  /** dataset_gen.opponent_past(PublicObserver.plays, view tick, seat, gid) -> out[off .. off + 15) (3 x 5): the last 3
   *  plays seen strictly before the view tick of the last estimateAt (tick + h), newest first, [checkpoint card id,
   *  form, x, y (my frame, obs_contract._engine_xy), seconds ago]; an empty or unknown-card row (0, 3, -1, -1, -1). */
  public void past(FloatBuffer out, int off) {
    final int t = viewTick;
    int i = n - 1;
    while (i >= 0 && ticks[i] >= t) i--;                           // plays are in (tick, charge) order already
    for (int r = 0; r < 3; r++, i--) {
      int o = off + r * 5;
      int c = i >= 0 ? keys.gid.get(pkey[i]) : 0;
      if (c == 0) {
        out.put(o, 0f); out.put(o + 1, 3f); out.put(o + 2, -1f); out.put(o + 3, -1f); out.put(o + 4, -1f);
        continue;
      }
      double x = px[i], y = py[i];
      if (seat == 1) { x = 18000.0 - x; y = 32000.0 - y; }
      out.put(o, c); out.put(o + 1, pform[i]);
      out.put(o + 2, (float) (x / 18000.0)); out.put(o + 3, (float) (1.0 - y / 32000.0));
      out.put(o + 4, (float) ((t - ticks[i]) * 0.05));
    }
  }
}
