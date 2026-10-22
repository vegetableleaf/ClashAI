"""W19 fork change (branch fin16 off fin15 305aaafc): the CLIENT-DATED 2026-10-19 balance update.
  python fork_oct19.py FORK_DIR
1. data/derived/cards-160402017-20261019.json = the 2026-10-06 table with the 10-19 changes (Skeletons summon radius 400 ->
   500 native; W23's numeric diffs are applied later with --diff FILE: {card: {field: value}}).
2. card.rs: the embedded copy + file / version constants + `CardDb::load_table` arm.
3. state.rs: CardTable::Client160402017Oct19 = "client160402017_20261019"; repo_cards' cell.
4. state.rs formation_members_with: on that table, a Skeletons deploy whose tap is on one of the two middle tile columns
   keeps each member's own creation lane (no summon_x): "always split when placed on middle tiles" (patch notes; live: the
   right member of a tap at x 8500 walks to the right lane, 6 of 6 W19 dossiers).
5. calibration.json: the new candidate and its provenance.
6. tests/card_table.rs: the new arm loads its table with the 500 ring, the 10-06 arm keeps 400; plant card_table_unread
   turns it red with the others."""
import json
import sys
from pathlib import Path

F = Path(sys.argv[1])
diff = json.loads(Path(sys.argv[sys.argv.index('--diff') + 1]).read_text()) if '--diff' in sys.argv else {}


def edit(path, old, new, count=1):
    p = F / path
    s = p.read_text()
    assert s.count(old) == count, (path, old[:80], s.count(old))
    p.write_text(s.replace(old, new))


# 1. the table
src = json.loads((F / 'data/derived/cards-160402017-20261006.json').read_text())
src['version'] = 'cards-160402017-20261019.1'
src['provenance'] = str(src.get('provenance', '')) + (' | 2026-10-19 balance update applied over the 2026-10-06 table (W19 '
                                                       'tools: parity/w19/fork_oct19.py; official notes via W23)')
n = 0
for c in src['cards']:
    if c['name'] == 'Skeletons':
        assert c['summon_radius_milli'] == 400
        c['summon_radius_milli'] = 500
        n += 1
    for field, v in (diff.get(c['name']) or {}).items():
        assert field in c, (c['name'], field)
        c[field] = v
        n += 1
assert n >= 1
(F / 'data/derived/cards-160402017-20261019.json').write_text(json.dumps(src, indent=1) + '\n')

# 2. card.rs
edit('crates/royalesim/src/card.rs', '''/// The install-time table's `version` (its file's own).
pub const CARDS_160402017_INSTALL_VERSION: &str = "cards-160402017.1";''', '''/// The install-time table's `version` (its file's own).
pub const CARDS_160402017_INSTALL_VERSION: &str = "cards-160402017.1";

/// THE 160402017 CLIENT AFTER THE 2026-10-19 BALANCE UPDATE: the 2026-10-06 table with that update's changes (the
/// Skeletons' summon radius 400 -> 500 native, "always split when placed on middle tiles" in `formation_members_with`),
/// compiled in: what a battle under cards.CARD_TABLE = client160402017_20261019 loads. Measured live (parity W19): from
/// 10-19 the three Skeletons stand on a symmetric ring of 580 (500 x 577 / 500, formation.rs `scale_radius`), and a tap
/// on a middle column splits them over both lanes.
pub const EMBEDDED_CARDS_160402017_20261019_JSON: &str = include_str!("../../../data/derived/cards-160402017-20261019.json");

/// The 2026-10-19 table's file name under data/derived/.
pub const CARDS_160402017_20261019_FILE: &str = "cards-160402017-20261019.json";

/// The 2026-10-19 table's `version` (its file's own).
pub const CARDS_160402017_20261019_VERSION: &str = "cards-160402017-20261019.1";''')
edit('crates/royalesim/src/card.rs', '''            crate::state::CardTable::Client160402017Install => {
                if cfg!(feature = "checkout-data") {''', '''            crate::state::CardTable::Client160402017Oct19 => {
                #[cfg(feature = "checkout-data")]
                if std::path::Path::new(&CardDb::repo_file_path(CARDS_160402017_20261019_FILE)).exists() {
                    return CardDb::load_repo_file(CARDS_160402017_20261019_FILE);
                }
                CardDb::from_json_str(EMBEDDED_CARDS_160402017_20261019_JSON, CardSource::Embedded)
            }
            crate::state::CardTable::Client160402017Install => {
                if cfg!(feature = "checkout-data") {''')

# 3. state.rs enum + cells
edit('crates/royalesim/src/state.rs', '''        Client160402017Install = "client160402017",
    }''', '''        Client160402017Install = "client160402017",
        /// The same client after the 2026-10-19 balance update (data/derived/cards-160402017-20261019.json,
        /// `EMBEDDED_CARDS_160402017_20261019_JSON`): the 10-06 table with that update's changes. What a capture recorded
        /// from 2026-10-19 on is scored against, and the table training runs on from then.
        Client160402017Oct19 = "client160402017_20261019",
    }''')
edit('crates/royalesim/src/state.rs', '''    static CELLS: [OnceLock<Result<Arc<CardDb>, String>>; 3] = [OnceLock::new(), OnceLock::new(), OnceLock::new()];
    let i = match t {
        CardTable::Client15535 => 0,
        CardTable::Client160402017 => 1,
        CardTable::Client160402017Install => 2,
    };''', '''    static CELLS: [OnceLock<Result<Arc<CardDb>, String>>; 4] = [OnceLock::new(), OnceLock::new(), OnceLock::new(), OnceLock::new()];
    let i = match t {
        CardTable::Client15535 => 0,
        CardTable::Client160402017 => 1,
        CardTable::Client160402017Install => 2,
        CardTable::Client160402017Oct19 => 3,
    };''')

# 4. the split rule
edit('crates/royalesim/src/state.rs', '''        let summon_x = (calib.first_tower_pick.spawn_lane() && total >= 2 && card.kind == CardKind::Troop && !(rings_only && self.lays_a_line(idx)))
            .then_some(pos.x);''', '''        // THE 2026-10-19 UPDATE (cards.CARD_TABLE = client160402017_20261019): the Skeletons "always split when placed on
        // middle tiles" -- a tap on one of the arena's two middle tile columns gives no summon_x, so each member keeps the
        // lane of its own creation point (`creation_lane`): live from 10-19, a tap at x 8500 sends the member standing at
        // x 9003 to the right lane (parity W19, 6 of 6 dossiers; before the update all three took the tap's lane).
        // PLANT (regression) skeletons_split_off: the new table still sends every member to the tap's lane.
        #[cfg(not(clash_plant = "skeletons_split_off"))]
        let split_middle = calib.card_table == CardTable::Client160402017Oct19
            && card.name == "Skeletons"
            && {
                let tile = pos.x / (self.cfg.arena.width / 18).max(1);
                tile == 8 || tile == 9
            };
        #[cfg(clash_plant = "skeletons_split_off")]
        let split_middle = false;
        let summon_x = (calib.first_tower_pick.spawn_lane() && total >= 2 && card.kind == CardKind::Troop && !(rings_only && self.lays_a_line(idx))
            && !split_middle)
            .then_some(pos.x);''')

# 5. calibration.json (both copies the build reads)
for cal in ('data/calibration.json',):
    p = F / cal
    s = p.read_text()
    old = '"candidates": ["client15535", "client160402017_20261006", "client160402017"],'
    assert s.count(old) == 1
    s = s.replace(old, '"candidates": ["client15535", "client160402017_20261006", "client160402017", "client160402017_20261019"],')
    p.write_text(s)

# 6. test
t = F / 'crates/royalesim/tests/card_table.rs'
t.write_text(t.read_text() + '''

/// THE 2026-10-19 ARM (client160402017_20261019): the 10-06 table with that update's changes -- the Skeletons' summon
/// radius 500 (400 on the 10-06 table, 700 on the install-time one). Plant card_table_unread loads 15.535.29 instead.
#[test]
fn the_2026_10_19_arm_loads_the_updated_skeleton_ring() {
    let c = arm("client160402017_20261019");
    assert_eq!(c.card_table, CardTable::Client160402017Oct19);
    let db = CardDb::load_table(c.card_table).expect("the 10-19 table loads");
    assert_eq!(db.version, royalesim::card::CARDS_160402017_20261019_VERSION);
    let r = |db: &CardDb| db.get(db.index("Skeletons").expect("Skeletons load")).formation.summon_radius;
    assert_eq!(r(&db), milli(500));
    let old = CardDb::load_table(CardTable::Client160402017).expect("the 10-06 table loads");
    assert_eq!(r(&old), milli(400));
}
''')
print('fork_oct19: applied;', n, 'card fields changed')
