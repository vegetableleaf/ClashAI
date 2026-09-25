// Read-only re-mapping of the upstream MuMu reader's root chain for the x86_64 libg build.
// Contract being re-mapped: research/ext/cr_live/upstream/bindings/mumu-live-160402002-arm64.json
//   libg_base + RVA -> manager (+0x28) -> context (+0x90) -> battle (+0x60 tick, +0xa8 player state
//   -> +0xe0/+0xe8 players -> +0x2f8 elixir raw, 10000 per point).
// v1 (exact arm64 offsets) found 1 chain whose tick did not advance, so v2 WIDENS every hop:
//   manager->context 0x08..0x60, context->battle 0x60..0xc0, and any int32 slot in battle[0x10..0x300)
//   that advances 1..60 across DELAY_MS (upstream found +0x60 the same way). Elixir is reported for each hit.
// Opens /proc/PID/mem O_RDONLY: no writes. Run DURING a live battle.
// Build (WSL): gcc -O2 -static -o chain_scan chain_scan.c      Run (root adb): chain_scan PID 500
#define _GNU_SOURCE
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_MAPS 8192
#define MAX_CHAINS 400000
#define MAX_BATTLES 40000
#define SPAN 0x300
#define HASH (1 << 17)  // > 2 * MAX_BATTLES, power of two
static int hidx[HASH];  // battle index + 1, 0 = empty

typedef struct { uint64_t start, end; int r, w; char path[256]; } Map;
typedef struct { uint64_t glob; int ro, co, bi; } Chain;
static Map maps[MAX_MAPS];
static int nmaps, fd;

static int rd(uint64_t a, void *out, size_t n) { return pread(fd, out, n, (off_t)a) == (ssize_t)n; }

static int writable(uint64_t a, size_t n) {
  if (a < 0x10000 || (a & 7)) return 0;
  for (int i = 0; i < nmaps; i++)
    if (maps[i].r && maps[i].w && a >= maps[i].start && a + n <= maps[i].end) return 1;
  return 0;
}

static uint64_t ptr(uint64_t a) { uint64_t v = 0; return rd(a, &v, 8) ? v : 0; }

static int32_t elixir(uint64_t bt, int side) {
  int32_t e = -1;
  uint64_t ps = ptr(bt + 0xa8);
  uint64_t pl = writable(ps, 0x100) ? ptr(ps + 0xe0 + 8 * side) : 0;
  if (writable(pl, 0x300)) rd(pl + 0x2f8, &e, 4);
  return e;
}

int main(int argc, char **argv) {
  if (argc != 3) { fprintf(stderr, "usage: chain_scan PID DELAY_MS\n"); return 2; }
  int pid = atoi(argv[1]), delay = atoi(argv[2]);
  char p[64];
  snprintf(p, sizeof p, "/proc/%d/maps", pid);
  FILE *f = fopen(p, "r");
  if (!f) return 3;
  char line[1024];
  while (nmaps < MAX_MAPS && fgets(line, sizeof line, f)) {
    unsigned long long s, e; char perm[8] = {0}; int used = 0;
    if (sscanf(line, "%llx-%llx %7s %*s %*s %*s %n", &s, &e, perm, &used) < 3) continue;
    Map *m = &maps[nmaps++];
    m->start = s; m->end = e; m->r = perm[0] == 'r'; m->w = perm[1] == 'w';
    snprintf(m->path, sizeof m->path, "%s", line + used);
    m->path[strcspn(m->path, "\r\n")] = 0;
  }
  fclose(f);
  uint64_t lo = UINT64_MAX, hi = 0;
  for (int i = 0; i < nmaps; i++)
    if (strstr(maps[i].path, "/libg.so")) {
      if (maps[i].start < lo) lo = maps[i].start;
      if (maps[i].end > hi) hi = maps[i].end;
    }
  if (!hi) { fprintf(stderr, "libg.so not mapped\n"); return 4; }
  snprintf(p, sizeof p, "/proc/%d/mem", pid);
  fd = open(p, O_RDONLY | O_CLOEXEC);
  if (fd < 0) return 5;

  Chain *ch = malloc(sizeof(Chain) * MAX_CHAINS);
  uint64_t *bts = malloc(8 * MAX_BATTLES);
  int32_t *snap = malloc((size_t)MAX_BATTLES * SPAN);
  if (!ch || !bts || !snap) return 6;
  int nc = 0, nb = 0, roots = 0;
  for (int i = 0; i < nmaps; i++) {
    Map *m = &maps[i];
    int in_libg = strstr(m->path, "/libg.so") != NULL;
    int bss = strstr(m->path, "[anon:.bss]") != NULL && m->start >= hi && m->start < hi + 0x1000000;
    if (!m->r || !m->w || !(in_libg || bss)) continue;
    size_t size = m->end - m->start;
    uint8_t *buf = malloc(size);
    if (!buf || !rd(m->start, buf, size)) { free(buf); continue; }
    for (size_t o = 0; o + 8 <= size; o += 8) {
      uint64_t root; memcpy(&root, buf + o, 8);
      if ((root >= lo && root < hi) || !writable(root, 0x100)) continue;
      roots++;
      for (int ro = 0x08; ro <= 0x60; ro += 8) {
        uint64_t ctx = ptr(root + ro);
        if ((ctx >= lo && ctx < hi) || !writable(ctx, 0x100)) continue;
        for (int co = 0x60; co <= 0xc0; co += 8) {
          uint64_t bt = ptr(ctx + co);
          if ((bt >= lo && bt < hi) || bt == root || bt == ctx || !writable(bt, SPAN)) continue;
          uint32_t h = (uint32_t)((bt >> 3) * 2654435761u) & (HASH - 1);
          while (hidx[h] && bts[hidx[h] - 1] != bt) h = (h + 1) & (HASH - 1);
          int bi = hidx[h] - 1;
          if (bi < 0) {
            if (nb >= MAX_BATTLES || !rd(bt, snap + (size_t)nb * (SPAN / 4), SPAN)) continue;
            bts[bi = nb++] = bt;
            hidx[h] = nb;
          }
          if (nc < MAX_CHAINS) ch[nc++] = (Chain){m->start + o, ro, co, bi};
        }
      }
    }
    free(buf);
  }
  for (int b = 0; b < nb; b++) rd(bts[b], snap + (size_t)b * (SPAN / 4), SPAN);  // fresh baseline: the scan itself takes seconds
  usleep((useconds_t)delay * 1000U);
  printf("{\"pid\":%d,\"libg_base\":\"0x%" PRIx64 "\",\"roots\":%d,\"chains\":%d,\"battles\":%d,\"hits\":[",
         pid, lo, roots, nc, nb);
  int32_t now[SPAN / 4];
  int k = 0;
  for (int b = 0; b < nb && k < 60; b++) {
    if (!rd(bts[b], now, SPAN)) continue;
    for (int s = 4; s < SPAN / 4 && k < 60; s++) {  // skip the header 0x00..0x0f
      int32_t old = snap[(size_t)b * (SPAN / 4) + s], d = now[s] - old;
      if (old < 20 || old > 1000000 || d < 1 || d > 60) continue;
      for (int c = 0; c < nc; c++) {
        if (ch[c].bi != b) continue;
        printf("%s{\"rva\":\"0x%" PRIx64 "\",\"ro\":\"0x%x\",\"co\":\"0x%x\",\"tick_off\":\"0x%x\","
               "\"tick\":[%d,%d],\"elixir_raw\":[%d,%d]}", k++ ? "," : "", ch[c].glob - lo, ch[c].ro, ch[c].co,
               s * 4, old, now[s], elixir(bts[b], 0), elixir(bts[b], 1));
        break;  // one chain per battle/slot is enough to report
      }
    }
  }
  printf("]}\n");
  close(fd);
  return 0;
}
