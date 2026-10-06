/*
 * Live sampler v2, live x86_64 build 160402012. READ-ONLY /proc/PID/mem.
 * Build in WSL, from this directory (NOT compiled in the sandbox):
 *   gcc -O2 -static -o live_sampler2 live_sampler2.c
 * Run: live_sampler2 PID 100 0x1aeef98 0x18 --unified 0 [--extended]
 * Only --extended adds evo and the projectiles/effects arrays, and admits the
 * table-13 evolution bodies that v1 incorrectly filters. Native IDs preserved.
 * Default formatting and original reader functions are retained. The new
 * vtables are pinned to this build; do not reuse on another game update.
 *
 * LEAD CHECKLIST after compiling:
 * [ ] Confirm x86_64 static ELF, O_RDONLY and no native-game calls/input.
 * [ ] Verify installed package build and libg identity before enabling fields.
 * [ ] Run standalone v1 and v2 default ~60s without disturbing the live bot.
 *     Use /data/local/tmp/re_* paths only under this task's write boundary.
 * [ ] Diff raw default JSON; record result. Independent reader_pid, sequence,
 *     sample_monotonic_us/read_us and sampling times naturally differ. Do not
 *     claim byte-identical live streams. For the formatter contract, compare
 *     deterministic identical frame fixtures byte-for-byte; also compare
 *     coherent same-tick live payloads with only documented volatile exclusions.
 * [ ] Compare --extended against Python reference on identical captured bytes.
 *     Check empty/inactive/error cases, projectile target and moving position,
 *     effect countdown (NOT sandbox elapsed time); negative timers emit null.
 * [ ] Confirm five independently labelled base/evolved Knight AND Tesla bodies
 *     per class, cast cycle and names; check opponents on an existing video if
 *     available. No new screenshot/video capture under the task authorization.
 * [ ] Measure read_us/coherence and adb load; do not replace the running reader
 *     or integrate with the live pilot under this task.
 *
 * Source SHA256: 80c26a986cf5a526ff0646f04797341ac34175da6f538923cc10f17579fe54a2
 * Evidence/limitations: FINDINGS.md, correlation.json, capture_*.jsonl.
 */
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

enum {
  BATTLE_TICK = 0x60,
  PLAYER_TABLE = 0xE0,
  PLAYER_HAND_VECTOR = 0x210,
  PLAYER_HAND_CAPACITY = 0x218,
  PLAYER_HAND_SIZE = 0x21C,
  PLAYER_CYCLE_VECTOR = 0x220,
  PLAYER_CYCLE_CAPACITY = 0x228,
  PLAYER_CYCLE_SIZE = 0x22C,
  PLAYER_DECK_COUNT = 0x230,
  PLAYER_ELIXIR_RAW = 0x2F8,
  MAX_DISCOVERY_NODES = 20000,
  MAX_DISCOVERY_DEPTH = 5,
  MAX_PATH_LENGTH = MAX_DISCOVERY_DEPTH + 2,
  MAX_ENTITIES = 2048,
};

typedef struct {
  uint64_t address;
  int32_t elixir_raw;
  int32_t refill_timer;
  int32_t next_deck_index;
  int32_t hand[4];
  int32_t hand_size;
  int32_t cycle[8];
  int32_t cycle_size;
  int32_t deck_count;
  int32_t deck_card_ids[8];
  int32_t deck_form_flags[8];
  int32_t deck_visible;
} PlayerFrame;

typedef struct {
  uint64_t address;
  int depth;
  uint16_t path[MAX_PATH_LENGTH];
} DiscoveryNode;

typedef struct {
  uint64_t battle, player_state, last_discovery_us;
  uint16_t path[MAX_PATH_LENGTH];
  int path_length;
} PlayerCache;

static int character_identity = 0;
#include "character_name.h"
typedef struct {
  uint64_t address;
  int32_t category, kind, side, x, y, card_id, level, hp, max_hp, behavior;
  char native_name[129];
  reader_character_status native_name_status;
  uint64_t attached_owner;
  int attached_owner_read_ok;
} EntityFrame;

typedef struct {
  uint64_t root, context, battle, player_state, hp_state, registry, collection, data;
  int32_t replay_tick, native_count, entity_count, filtered_count;
  int discovery_nodes, discovery_budget_exhausted;
  const char *failure;
  EntityFrame entities[MAX_ENTITIES];
} ChainFrame;

static int read_exact(int fd, uint64_t address, void *output, size_t size) {
  uint8_t *cursor = (uint8_t *)output;
  size_t done = 0;
  while (done < size) {
    ssize_t value = pread(fd, cursor + done, size - done,
                          (off_t)(address + done));
    if (value <= 0) return 0;
    done += (size_t)value;
  }
  return 1;
}

static int character_read(void *context, uint64_t address, void *out, size_t size) {
  return read_exact(*(int *)context, address, out, size);
}
static void read_character_metadata(int fd, ChainFrame *frame) {
  for (int i=0; i<frame->entity_count; ++i) {
    EntityFrame *e=&frame->entities[i];
    if (e->card_id != 203000023) continue;
    e->native_name_status=reader_character_name(character_read, &fd, e->address,
      e->native_name, &e->attached_owner, &e->attached_owner_read_ok);
  }
}

static uint64_t monotonic_us(void) {
  struct timespec value;
  clock_gettime(CLOCK_MONOTONIC, &value);
  return (uint64_t)value.tv_sec * 1000000ULL +
         (uint64_t)value.tv_nsec / 1000ULL;
}

static uint64_t find_libg_base(int pid) {
  char maps_path[64];
  char line[1024];
  uint64_t best = UINT64_MAX;
  snprintf(maps_path, sizeof(maps_path), "/proc/%d/maps", pid);
  FILE *maps = fopen(maps_path, "r");
  if (!maps) return 0;
  while (fgets(line, sizeof(line), maps)) {
    unsigned long long start = 0;
    unsigned long long offset = 0;
    char permissions[8] = {0};
    if (!strstr(line, "/libg.so")) continue;
    if (sscanf(line, "%llx-%*llx %7s %llx", &start, permissions, &offset) !=
        3)
      continue;
    if ((uint64_t)start >= (uint64_t)offset &&
        (uint64_t)start - (uint64_t)offset < best)
      best = (uint64_t)start - (uint64_t)offset;
  }
  fclose(maps);
  return best == UINT64_MAX ? 0 : best;
}

static int valid_index(int32_t value, int32_t deck_count, int allow_empty) {
  if (allow_empty && value == -1) return 1;
  return value >= 0 && value < deck_count;
}

static int read_player(int fd, uint64_t player, PlayerFrame *out) {
  uint64_t hand_vector = 0, cycle_vector = 0;
  int32_t hand_capacity = -1, cycle_capacity = -1;
  memset(out, 0, sizeof(*out));
  out->address = player;
  out->refill_timer = 0;
  out->deck_count = 8;
  out->next_deck_index = -1;
  for (int index = 0; index < 4; ++index) out->hand[index] = -1;
  if (!player ||
      !read_exact(fd, player + PLAYER_ELIXIR_RAW, &out->elixir_raw, 4) ||
      !read_exact(fd, player + PLAYER_HAND_VECTOR, &hand_vector, 8) ||
      !read_exact(fd, player + PLAYER_HAND_CAPACITY, &hand_capacity, 4) ||
      !read_exact(fd, player + PLAYER_HAND_SIZE, &out->hand_size, 4) ||
      !read_exact(fd, player + PLAYER_CYCLE_VECTOR, &cycle_vector, 8) ||
      !read_exact(fd, player + PLAYER_CYCLE_CAPACITY, &cycle_capacity, 4) ||
      !read_exact(fd, player + PLAYER_CYCLE_SIZE, &out->cycle_size, 4))
    return 0;
  if (out->elixir_raw < 0 || out->elixir_raw > 100000 ||
      hand_capacity < 4 || hand_capacity > 8 || out->hand_size != 4 ||
      cycle_capacity < 0 || cycle_capacity > 8 ||
      out->cycle_size < 0 || out->cycle_size > cycle_capacity ||
      (out->hand_size && !hand_vector) ||
      (out->cycle_size && !cycle_vector))
    return 0;
  if (out->hand_size &&
      !read_exact(fd, hand_vector, out->hand,
                  (size_t)out->hand_size * sizeof(out->hand[0])))
    return 0;
  if (out->cycle_size &&
      !read_exact(fd, cycle_vector, out->cycle,
                  (size_t)out->cycle_size * sizeof(out->cycle[0])))
    return 0;
  for (int index = 0; index < out->hand_size; ++index)
    if (!valid_index(out->hand[index], out->deck_count, 1)) return 0;
  for (int index = 0; index < out->cycle_size; ++index)
    if (!valid_index(out->cycle[index], out->deck_count, 0)) return 0;
  if (out->cycle_size > 0) out->next_deck_index = out->cycle[0];
  return 1;
}

static int read_visible_deck(int fd, PlayerFrame *player) {
  int visible = 0;
  for (int index = 0; index < 4; ++index)
    if (player->hand[index] >= 0) visible = 1;
  if (!visible) return 1;
  uint64_t context = 0, root = 0, avatar = 0, owner = 0, entries = 0;
  int32_t side = -1, count = -1, identity = -1;
  int32_t account_hi = 0, account_lo = 0, entry_count = -1;
  if (!read_exact(fd, player->address + 0x10, &context, 8) || !context ||
      !read_exact(fd, context + 0x98, &root, 8) || !root ||
      !read_exact(fd, player->address + 0x78, &side, 4) ||
      side < 0 || side > 5 ||
      !read_exact(fd, root + 0x30 + (uint64_t)side * 8, &avatar, 8) ||
      !avatar || !read_exact(fd, avatar, &account_hi, 4) ||
      !read_exact(fd, avatar + 4, &account_lo, 4) ||
      !read_exact(fd, root + 0x60, &count, 4) || count < 1 || count > 6)
    return 0;
  for (int index = 0; index < count; ++index) {
    uint64_t candidate = 0;
    int32_t hi = 0, lo = 0;
    if (!read_exact(fd, root + 0x30 + (uint64_t)index * 8,
                    &candidate, 8) || !candidate ||
        !read_exact(fd, candidate, &hi, 4) ||
        !read_exact(fd, candidate + 4, &lo, 4))
      continue;
    if (hi == account_hi && lo == account_lo) {
      identity = index;
      break;
    }
  }
  if (identity < 0 ||
      !read_exact(fd, root + 0x88 + (uint64_t)identity * 8, &owner, 8) ||
      !owner || !read_exact(fd, owner + 0x20, &entries, 8) || !entries ||
      !read_exact(fd, owner + 0x2c, &entry_count, 4) || entry_count != 8)
    return 0;
  for (int index = 0; index < 8; ++index) {
    uint64_t entry = 0, data = 0;
    if (!read_exact(fd, entries + (uint64_t)index * 8, &entry, 8) || !entry ||
        !read_exact(fd, entry + 0x10, &data, 8) || !data ||
        !read_exact(fd, data + 0x40, &player->deck_card_ids[index], 4) ||
        !read_exact(fd, entry + 0x1c, &player->deck_form_flags[index], 4))
      return 0;
    int32_t card_id = player->deck_card_ids[index];
    int32_t form = player->deck_form_flags[index];
    if (card_id < 25000000 || card_id > 29999999 || form < 0 || form > 2)
      return 0;
  }
  player->deck_visible = 1;
  return 1;
}

static int read_player_pair(int fd, uint64_t player_state,
                            PlayerFrame players[2]) {
  uint64_t addresses[2] = {0, 0};
  return player_state &&
         read_exact(fd, player_state + PLAYER_TABLE, addresses,
                    sizeof(addresses)) &&
         read_player(fd, addresses[0], &players[0]) &&
         read_player(fd, addresses[1], &players[1]) &&
         read_visible_deck(fd, &players[0]) &&
         read_visible_deck(fd, &players[1]);
}

static int seen_insert(uint64_t *table, size_t capacity, uint64_t value) {
  size_t index = (size_t)((value >> 3) * 11400714819323198485ull) &
                 (capacity - 1);
  for (size_t attempt = 0; attempt < capacity; ++attempt) {
    if (table[index] == value) return 0;
    if (table[index] == 0) {
      table[index] = value;
      return 1;
    }
    index = (index + 1) & (capacity - 1);
  }
  return 0;
}

static uint64_t discover_player_state(int fd, uint64_t battle,
                                      PlayerFrame players[2], PlayerCache *cache,
                                      ChainFrame *frame) {
  enum { SEEN_CAPACITY = 32768 };
  DiscoveryNode *nodes = calloc(MAX_DISCOVERY_NODES, sizeof(*nodes));
  uint64_t *seen = calloc(SEEN_CAPACITY, sizeof(*seen));
  if (!nodes || !seen) {
    free(nodes);
    free(seen);
    return 0;
  }
  int count = 1;
  uint64_t started = monotonic_us();
  nodes[0].address = battle;
  seen_insert(seen, SEEN_CAPACITY, battle);
  for (int cursor = 0; cursor < count; ++cursor) {
    if ((cursor & 63) == 0 && monotonic_us() - started > 20000) {
      frame->discovery_budget_exhausted = 1;
      break;
    }
    frame->discovery_nodes = cursor + 1;
    DiscoveryNode node = nodes[cursor];
    if (read_player_pair(fd, node.address, players)) {
      cache->path_length = node.depth;
      memcpy(cache->path, node.path, sizeof(cache->path));
      free(nodes);
      free(seen);
      return node.address;
    }
    uint64_t context = 0, indirect_state = 0;
    if (read_exact(fd, node.address + 0x10, &context, 8) && context &&
        read_exact(fd, context + 0x98, &indirect_state, 8) &&
        read_player_pair(fd, indirect_state, players)) {
      cache->path_length = node.depth + 2;
      memcpy(cache->path, node.path, sizeof(cache->path));
      cache->path[node.depth] = 0x10;
      cache->path[node.depth + 1] = 0x98;
      free(nodes);
      free(seen);
      return indirect_state;
    }
    if (node.depth >= MAX_DISCOVERY_DEPTH) continue;
    uint8_t raw[0x600];
    if (!read_exact(fd, node.address, raw, sizeof(raw))) continue;
    for (size_t offset = 0;
         offset + sizeof(uint64_t) <= sizeof(raw) &&
         count < MAX_DISCOVERY_NODES;
         offset += sizeof(uint64_t)) {
      uint64_t child = 0, probe = 0;
      memcpy(&child, raw + offset, sizeof(child));
      if (child < 0x10000ull || (child & 7) ||
          !seen_insert(seen, SEEN_CAPACITY, child) ||
          !read_exact(fd, child, &probe, sizeof(probe)))
        continue;
      nodes[count].address = child;
      nodes[count].depth = node.depth + 1;
      memcpy(nodes[count].path, node.path, sizeof(node.path));
      nodes[count].path[node.depth] = (uint16_t)offset;
      ++count;
    }
  }
  free(nodes);
  free(seen);
  return 0;
}

static int read_entities(int fd, ChainFrame *frame) {
  uint64_t addresses[MAX_ENTITIES];
  if (!read_exact(fd, frame->battle + 0xA8, &frame->hp_state, 8) || !frame->hp_state ||
      !read_exact(fd, frame->hp_state + 0x08, &frame->registry, 8) || !frame->registry ||
      !read_exact(fd, frame->registry + 0x40, &frame->collection, 8) || !frame->collection ||
      !read_exact(fd, frame->collection + 0x08, &frame->data, 8) ||
      !read_exact(fd, frame->collection + 0x14, &frame->native_count, 4) ||
      frame->native_count < 0 || frame->native_count > MAX_ENTITIES ||
      (frame->native_count && (!frame->data || !read_exact(fd, frame->data, addresses,
          (size_t)frame->native_count * sizeof(addresses[0]))))) return 0;
  for (int i = 0; i < frame->native_count; ++i) {
    uint8_t raw[0x124];
    if (!addresses[i] || !read_exact(fd, addresses[i], raw, sizeof(raw))) return 0;
    EntityFrame item = {.address = addresses[i], .hp = -1, .max_hp = -1};
    memcpy(&item.category, raw + 0x08, 4);
    memcpy(&item.kind, raw + 0x30, 4);
    memcpy(&item.side, raw + 0x78, 4);
    memcpy(&item.x, raw + 0x7C, 4);
    memcpy(&item.y, raw + 0x80, 4);
    memcpy(&item.card_id, raw + 0xAC, 4);
    memcpy(&item.level, raw + 0x120, 4);
    memcpy(&item.behavior, raw + 0x11C, 4);
    if (item.category < 5000000 || item.category >= 6000000 ||
        item.kind < 10 || item.kind > 20 || item.side < 0 || item.side > 1 ||
        item.x < 0 || item.x > 18000 || item.y < 0 || item.y > 32000 ||
        item.level < 0 || item.level > 16 ||
        (item.card_id != -1 && (item.card_id < 20000000 || item.card_id >= 1000000000))) {
      frame->filtered_count++;
      continue;
    }
    item.level++;
    uint64_t components = 0, hp = 0;
    memcpy(&components, raw + 0x18, 8);
    if (components && read_exact(fd, components + 0x10, &hp, 8) && hp) {
      int32_t pair[2];
      if (read_exact(fd, hp + 0x10, pair, sizeof(pair)) && pair[0] >= 0 &&
          pair[1] >= pair[0] && pair[1] <= 100000) {
        item.hp = pair[0]; item.max_hp = pair[1];
      }
    }
    frame->entities[frame->entity_count++] = item;
  }
  return 1;
}

/* Included textually into live_sampler2.c by build_source.py; no game calls. */
enum { EXT_PROJECTILE_VT = 0x19f7370, EXT_AREA_VT = 0x19f6a28 };
static int extended = 0;
typedef struct {
  uint64_t address, vtable_rva, source, target, attached_owner, data_ptr;
  int32_t generation_key, side, x, y, card_id, target_x, target_y;
  int32_t timer_ms_raw, life_override_ms_raw, level;
  int64_t remaining_ms;
} ExtraObject;
typedef struct {
  ExtraObject projectiles[MAX_ENTITIES], effects[MAX_ENTITIES];
  int projectile_count, effect_count, unknown_nonunits, read_errors;
} ExtraFrame;
static ExtraFrame extra;

static int32_t ext_i32(const uint8_t *b, size_t o) {
  int32_t v; memcpy(&v, b + o, 4); return v;
}
static uint64_t ext_u64(const uint8_t *b, size_t o) {
  uint64_t v; memcpy(&v, b + o, 8); return v;
}
static int ext_evo(int32_t card_id) {
  /* This live build uses table 13 form IDs; v1 discarded those bodies.
     A deck evolution eligibility flag is NOT a spawned-body evolution flag. */
  return card_id >= 13000000 && card_id < 14000000;
}
static void read_extended_objects(int fd, uint64_t libg, ChainFrame *frame) {
  uint64_t addresses[MAX_ENTITIES];
  memset(&extra, 0, sizeof(extra));
  if (frame->native_count < 0 || frame->native_count > MAX_ENTITIES ||
      (frame->native_count && (!frame->data ||
       !read_exact(fd, frame->data, addresses, (size_t)frame->native_count * 8)))) {
    extra.read_errors++; return;
  }
  for (int j = 0; j < frame->native_count; ++j) {
    uint8_t raw[0x128];
    if (!addresses[j] || !read_exact(fd, addresses[j], raw, sizeof raw)) {
      extra.read_errors++; continue;
    }
    uint64_t vt = ext_u64(raw, 0);
    uint64_t rva = vt >= libg ? vt - libg : UINT64_MAX;
    int32_t category = ext_i32(raw, 8), side = ext_i32(raw, 0x78);
    int32_t card = ext_i32(raw, 0xac), x = ext_i32(raw, 0x7c), y = ext_i32(raw, 0x80);
    if (category >= 5000000 && category < 6000000 && ext_evo(card)) {
      EntityFrame e = {.address = addresses[j], .category = category,
        .kind = ext_i32(raw, 0x30), .side = side, .x = x, .y = y,
        .card_id = card, .level = ext_i32(raw, 0x120),
        .behavior = ext_i32(raw, 0x11c), .hp = -1, .max_hp = -1};
      if (e.kind < 10 || e.kind > 20 || side < 0 || side > 1 ||
          x < 0 || x > 18000 || y < 0 || y > 32000 ||
          e.level < 0 || e.level > 16 || frame->entity_count >= MAX_ENTITIES) continue;
      uint64_t components = ext_u64(raw, 0x18), hp = 0;
      int32_t pair[2];
      if (components && read_exact(fd, components + 0x10, &hp, 8) && hp &&
          read_exact(fd, hp + 0x10, pair, sizeof pair) && pair[0] >= 0 &&
          pair[1] >= pair[0] && pair[1] <= 100000) {
        e.hp = pair[0]; e.max_hp = pair[1];
      }
      e.level++;
      /* Guard against a second registry read seeing a reused address or duplicate. */
      int duplicate = 0;
      for (int k = 0; k < frame->entity_count; ++k)
        if (frame->entities[k].address == e.address) { duplicate = 1; break; }
      if (!duplicate) {
        frame->entities[frame->entity_count++] = e;
        if (frame->filtered_count > 0) frame->filtered_count--;
      }
      continue;
    }
    if (category < 3000000 || category >= 5000000) continue;
    int projectile = rva == EXT_PROJECTILE_VT && category >= 4000000;
    int effect = rva == EXT_AREA_VT && category < 4000000;
    if ((!projectile && !effect) || side < 0 || side > 1) {
      extra.unknown_nonunits++; continue;
    }
    ExtraObject o = {.address = addresses[j], .vtable_rva = rva,
      .generation_key = category, .side = side, .x = x, .y = y, .card_id = card,
      .data_ptr = ext_u64(raw, 0x48), .remaining_ms = -1};
    if (projectile) {
      o.source = ext_u64(raw, 0x100); o.target = ext_u64(raw, 0x108);
      o.attached_owner = ext_u64(raw, 0x118);
      o.target_x = ext_i32(raw, 0x120); o.target_y = ext_i32(raw, 0x124);
      if (extra.projectile_count < MAX_ENTITIES)
        extra.projectiles[extra.projectile_count++] = o;
    } else {
      o.timer_ms_raw = ext_i32(raw, 0x100); o.level = ext_i32(raw, 0xfc);
      o.life_override_ms_raw = ext_i32(raw, 0x114);
      /* Live Tornado: tick 818 => 400, tick 825 => 50. This is a
         countdown, NOT the sandbox bridge's assumed elapsed time. Do not
         carry that build's data+0x170 lifetime formula into this build. */
      if (o.timer_ms_raw >= 0) o.remaining_ms = o.timer_ms_raw;
      if (extra.effect_count < MAX_ENTITIES) extra.effects[extra.effect_count++] = o;
    }
  }
}

static void emit_extended_entity(const EntityFrame *e) {
  printf("{\"address\":\"0x%" PRIx64 "\",\"category\":%d,\"kind\":%d,\"side\":%d,"
         "\"x\":%d,\"y\":%d,\"card_id\":%d,\"level\":%d,\"hp\":%d,\"max_hp\":%d,"
         "\"behavior_state_raw\":%d,\"evo\":%d", e->address, e->category, e->kind, e->side,
         e->x, e->y, e->card_id, e->level, e->hp, e->max_hp, e->behavior, ext_evo(e->card_id));
  if (character_identity && e->card_id == 203000023) {
    printf(",\"native_name_status\":\"%s\",\"native_name\":", reader_character_status_name(e->native_name_status));
    if (e->native_name_status == READER_CHARACTER_OK) printf("\"%s\"", e->native_name); else printf("null");
    printf(",\"attached_owner_read_ok\":%s,\"attached_owner\":", e->attached_owner_read_ok ? "true" : "false");
    if (e->attached_owner_read_ok) printf("\"0x%" PRIx64 "\"", e->attached_owner); else printf("null");
  }
  putchar('}');
}
static void emit_optional_pointer(uint64_t p) {
  if (p) printf("\"0x%" PRIx64 "\"", p); else printf("null");
}
static void emit_extra(int active, int coherent) {
  /* The caller's tick/chain bracket covers these reads. Suppress nonunit
     payload on a failed or incoherent frame and expose validity explicitly. */
  int valid = active && coherent && extra.read_errors == 0;
  printf(",\"extension\":{\"build\":160402012,\"valid\":%s,"
         "\"evo_basis\":\"card_id_table_13\",\"unknown_nonunits\":%d,\"read_errors\":%d},"
         "\"projectiles\":[", valid ? "true" : "false", extra.unknown_nonunits, extra.read_errors);
  for (int i = 0; valid && i < extra.projectile_count; ++i) {
    const ExtraObject *o = &extra.projectiles[i];
    printf("%s{\"address\":\"0x%" PRIx64 "\",\"generation_key\":%d,\"vtable_rva\":\"0x%" PRIx64
           "\",\"side\":%d,\"x\":%d,\"y\":%d,\"target_x\":%d,\"target_y\":%d,\"card_id\":%d,\"source\":",
           i ? "," : "", o->address, o->generation_key, o->vtable_rva, o->side, o->x, o->y,
           o->target_x, o->target_y, o->card_id);
    emit_optional_pointer(o->source); printf(",\"target\":"); emit_optional_pointer(o->target);
    printf(",\"attached_owner\":"); emit_optional_pointer(o->attached_owner); putchar('}');
  }
  printf("],\"effects\":[");
  for (int i = 0; valid && i < extra.effect_count; ++i) {
    const ExtraObject *o = &extra.effects[i];
    printf("%s{\"address\":\"0x%" PRIx64 "\",\"generation_key\":%d,\"vtable_rva\":\"0x%" PRIx64
           "\",\"side\":%d,\"x\":%d,\"y\":%d,\"card_id\":%d,\"data_ptr\":\"0x%" PRIx64
           "\",\"level_raw\":%d,\"timer_ms_raw\":%d,\"life_override_ms_raw\":%d,\"remaining_ms\":",
           i ? "," : "", o->address, o->generation_key, o->vtable_rva, o->side, o->x, o->y,
           o->card_id, o->data_ptr, o->level, o->timer_ms_raw, o->life_override_ms_raw);
    if (o->remaining_ms < 0) printf("null"); else printf("%" PRId64, o->remaining_ms);
    putchar('}');
  }
  putchar(']');
}

static int read_frame(int fd, uint64_t libg, uint64_t manager_rva,
                      uint64_t root_context_offset, int32_t *tick,
                      int *coherent, PlayerFrame players[2],
                      PlayerCache *cache, ChainFrame *frame, int unified) {
  uint64_t root = 0, context = 0, battle = 0;
  int32_t before = -1, after = -1;
  *tick = -1;
  *coherent = 1;
  memset(frame, 0, sizeof(*frame));
  frame->replay_tick = -1;
  frame->failure = "root_unresolved";
  if (!read_exact(fd, libg + manager_rva, &root, 8) || !root ||
      !read_exact(fd, root + root_context_offset, &context, 8) || !context ||
      !read_exact(fd, context + 0x90, &battle, 8) || !battle ||
      !read_exact(fd, battle + BATTLE_TICK, &before, 4) || before < 0)
    return 0;
  frame->root = root; frame->context = context; frame->battle = battle;
  frame->failure = "players_unresolved";
  if (cache->battle != battle) {
    memset(cache, 0, sizeof(*cache));
    cache->battle = battle;
  }
  if (!cache->player_state) {
    uint64_t direct = 0;
    if (read_exact(fd, battle + 0xA8, &direct, 8) && read_player_pair(fd, direct, players)) {
      cache->player_state = direct;
      cache->path_length = 1;
      cache->path[0] = 0xA8;
    }
  }
  uint64_t reached = battle;
  for (int i = 0; i < cache->path_length; ++i) {
    if (!reached || !read_exact(fd, reached + cache->path[i], &reached, 8)) { reached = 0; break; }
  }
  if (!cache->player_state || reached != cache->player_state ||
      !read_player_pair(fd, cache->player_state, players)) {
    cache->player_state = 0;
    /* The version-pinned unified reader accepts only the measured +0xA8
       path. Loading/menu state is not a reason to search unrelated objects. */
    if (unified) return 0;
    uint64_t now = monotonic_us();
    if (cache->last_discovery_us && now - cache->last_discovery_us < 1000000) return 0;
    cache->last_discovery_us = now;
    cache->player_state = discover_player_state(fd, battle, players, cache, frame);
    if (!cache->player_state) return 0;
  }
  frame->player_state = cache->player_state;
  frame->failure = "entities_unresolved";
  if (unified && !read_entities(fd, frame)) return 0;
  if (extended && unified) read_extended_objects(fd, libg, frame);
  if (character_identity && unified) read_character_metadata(fd, frame);
  read_exact(fd, battle + 0x1BC, &frame->replay_tick, 4);
  frame->failure = "incoherent_frame";
  if (!read_exact(fd, battle + BATTLE_TICK, &after, 4)) return 0;
  uint64_t root_after = 0, context_after = 0, battle_after = 0;
  if (!read_exact(fd, libg + manager_rva, &root_after, 8) || root_after != root ||
      !read_exact(fd, root_after + root_context_offset, &context_after, 8) || context_after != context ||
      !read_exact(fd, context_after + 0x90, &battle_after, 8) || battle_after != battle) {
    *coherent = 0;
    return 0;
  }
  *tick = after;
  *coherent = before == after;
  if (*coherent) frame->failure = "none";
  return 1;
}

static void emit_chain(const ChainFrame *f, const PlayerCache *cache, uint64_t libg) {
  printf(",\"chain\":{\"libg_base\":\"0x%" PRIx64 "\",\"root\":\"0x%" PRIx64
         "\",\"context\":\"0x%" PRIx64 "\",\"battle\":\"0x%" PRIx64
         "\",\"player_state\":\"0x%" PRIx64 "\",\"hp_state\":\"0x%" PRIx64
         "\",\"registry\":\"0x%" PRIx64 "\",\"collection\":\"0x%" PRIx64
         "\",\"data\":\"0x%" PRIx64 "\",\"player_state_path\":[",
         libg, f->root, f->context, f->battle, f->player_state, f->hp_state, f->registry, f->collection, f->data);
  for (int i = 0; i < cache->path_length; ++i) { if (i) putchar(','); printf("%u", cache->path[i]); }
  printf("]},\"failure\":\"%s\",\"applied_replay_tick\":%d,\"native_object_count\":%d,"
         "\"decoded_entity_count\":%d,\"filtered_object_count\":%d,\"discovery_nodes\":%d,"
         "\"discovery_budget_exhausted\":%s", f->failure, f->replay_tick, f->native_count,
         f->entity_count, f->filtered_count, f->discovery_nodes, f->discovery_budget_exhausted ? "true" : "false");
}

static void emit_player(const PlayerFrame *player, int side) {
  printf("{\"side\":%d,\"address\":\"0x%" PRIx64
         "\",\"elixir_raw\":%d,\"refill_timer\":%d,"
         "\"next_deck_index\":%d,\"hand_deck_indices\":[%d,%d,%d,%d],"
         "\"cycle_deck_indices\":[",
         side, player->address, player->elixir_raw, player->refill_timer,
         player->next_deck_index, player->hand[0], player->hand[1],
         player->hand[2], player->hand[3]);
  for (int index = 0; index < player->cycle_size; ++index) {
    if (index) putchar(',');
    printf("%d", player->cycle[index]);
  }
  printf("],\"deck_card_ids\":[");
  if (player->deck_visible) {
    for (int index = 0; index < 8; ++index) {
      if (index) putchar(',');
      printf("%d", player->deck_card_ids[index]);
    }
  }
  printf("],\"deck_form_flags\":[");
  if (player->deck_visible) {
    for (int index = 0; index < 8; ++index) {
      if (index) putchar(',');
      printf("%d", player->deck_form_flags[index]);
    }
  }
  printf("]}");
}

int main(int argc, char **argv) {
  if (argc != 5 && argc != 7 && argc != 8 && argc != 9) {
    fprintf(stderr,
            "usage: mumu-live-private PID INTERVAL_MS MANAGER_RVA "
            "ROOT_CONTEXT_OFFSET [--unified MAX_FRAMES(0=unlimited) [--extended]]\n");
    return 2;
  }
  int pid = atoi(argv[1]);
  int interval_ms = atoi(argv[2]);
  uint64_t manager_rva = strtoull(argv[3], NULL, 0);
  uint64_t root_context_offset = strtoull(argv[4], NULL, 0);
  int unified = argc >= 7;
  extended = argc >= 8;
  character_identity = argc == 9;
  if (character_identity && strcmp(argv[8], "--character-identity")) return 2;
  if (extended && strcmp(argv[7], "--extended")) return 2;
  uint64_t max_frames = unified ? strtoull(argv[6], NULL, 10) : 0;
  if (unified && strcmp(argv[5], "--unified")) return 2;
  if (pid <= 0 || interval_ms < 20 || interval_ms > 5000 || !manager_rva ||
      !root_context_offset)
    return 2;
  uint64_t libg = find_libg_base(pid);
  if (!libg) return 3;
  char memory_path[64];
  snprintf(memory_path, sizeof(memory_path), "/proc/%d/mem", pid);
  int fd = open(memory_path, O_RDONLY | O_CLOEXEC);
  if (fd < 0) return 4;
  setvbuf(stdout, NULL, _IONBF, 0);
  uint64_t sequence = 0;
  PlayerCache cache = {0};
  ChainFrame *frame = calloc(1, sizeof(*frame));
  if (!frame) { close(fd); return 5; }
  PlayerFrame players[2];
  while ((!max_frames || sequence < max_frames) && (kill(pid, 0) == 0 || errno == EPERM)) {
    uint64_t started = monotonic_us();
    int32_t tick = -1;
    int coherent = 1;
    int active = 0;
    for (int attempt = 0; attempt < 3; ++attempt) {
      if (extended) memset(&extra, 0, sizeof extra);
      active = read_frame(fd, libg, manager_rva, root_context_offset, &tick,
                          &coherent, players, &cache, frame, unified);
      if (!active || coherent) break;
    }
    printf("{\"event\":\"%s\",\"schema_version\":2,\"pid\":%d,\"reader_pid\":%d,\"sequence\":%" PRIu64
           ",\"battle_active\":%s,\"coherent\":%s,\"game_tick\":%d,"
           "\"players\":[",
           unified ? "mumu_live_frame" : "mumu_live_private", pid, getpid(), sequence++, active ? "true" : "false",
           coherent ? "true" : "false", tick);
    if (active) {
      emit_player(&players[0], 0);
      putchar(',');
      emit_player(&players[1], 1);
    }
    putchar(']');
    emit_chain(frame, &cache, libg);
    if (character_identity) printf(",\"character_identity\":{\"schema\":1,\"build\":160402012}");
    if (unified) {
      printf(",\"entities\":[");
      for (int i = 0; active && i < frame->entity_count; ++i) {
        const EntityFrame *e = &frame->entities[i];
        if (i) putchar(',');
        if (extended) { emit_extended_entity(e); continue; }
        printf("{\"address\":\"0x%" PRIx64 "\",\"category\":%d,\"kind\":%d,\"side\":%d,"
               "\"x\":%d,\"y\":%d,\"card_id\":%d,\"level\":%d,\"hp\":%d,\"max_hp\":%d,"
               "\"behavior_state_raw\":%d}", e->address, e->category, e->kind, e->side,
               e->x, e->y, e->card_id, e->level, e->hp, e->max_hp, e->behavior);
      }
      putchar(']');
    }
    if (extended) emit_extra(active, coherent);
    printf(",\"sample_monotonic_us\":%" PRIu64 ",\"read_us\":%" PRIu64 "}\n", started, monotonic_us() - started);
    uint64_t elapsed = monotonic_us() - started;
    uint64_t target = (uint64_t)interval_ms * 1000ULL;
    if (elapsed < target) usleep((useconds_t)(target - elapsed));
  }
  close(fd);
  free(frame);
  return 0;
}
