"""Create a separate additive reader; never edit or install the running reader."""
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
ORIGINAL=ROOT/'scratchpad/gauntlet/L70/reader/live_sampler2.c'

def build():
    text=ORIGINAL.read_text()
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,old
        text=text.replace(old,new)
    replace('typedef struct {\n  uint64_t address;\n  int32_t category, kind, side, x, y, card_id, level, hp, max_hp, behavior;\n} EntityFrame;',
        'static int character_identity = 0;\n#include "character_name.h"\n'
        'typedef struct {\n  uint64_t address;\n  int32_t category, kind, side, x, y, card_id, level, hp, max_hp, behavior;\n'
        '  char native_name[129];\n  reader_character_status native_name_status;\n'
        '  uint64_t attached_owner;\n  int attached_owner_read_ok;\n} EntityFrame;')
    replace('static uint64_t monotonic_us(void) {',
        'static int character_read(void *context, uint64_t address, void *out, size_t size) {\n'
        '  return read_exact(*(int *)context, address, out, size);\n}\n'
        'static void read_character_metadata(int fd, ChainFrame *frame) {\n'
        '  for (int i=0; i<frame->entity_count; ++i) {\n'
        '    EntityFrame *e=&frame->entities[i];\n'
        '    if (e->card_id != 203000023) continue;\n'
        '    e->native_name_status=reader_character_name(character_read, &fd, e->address,\n'
        '      e->native_name, &e->attached_owner, &e->attached_owner_read_ok);\n'
        '  }\n}\n\nstatic uint64_t monotonic_us(void) {')
    replace('  if (extended && unified) read_extended_objects(fd, libg, frame);',
        '  if (extended && unified) read_extended_objects(fd, libg, frame);\n'
        '  if (character_identity && unified) read_character_metadata(fd, frame);')
    replace('"\\\"behavior_state_raw\\\":%d,\\\"evo\\\":%d}",',
        '"\\\"behavior_state_raw\\\":%d,\\\"evo\\\":%d",')
    replace('         e->x, e->y, e->card_id, e->level, e->hp, e->max_hp, e->behavior, ext_evo(e->card_id));\n}',
        '         e->x, e->y, e->card_id, e->level, e->hp, e->max_hp, e->behavior, ext_evo(e->card_id));\n'
        '  if (character_identity && e->card_id == 203000023) {\n'
        '    printf(",\\\"native_name_status\\\":\\\"%s\\\",\\\"native_name\\\":", reader_character_status_name(e->native_name_status));\n'
        '    if (e->native_name_status == READER_CHARACTER_OK) printf("\\\"%s\\\"", e->native_name); else printf("null");\n'
        '    printf(",\\\"attached_owner_read_ok\\\":%s,\\\"attached_owner\\\":", e->attached_owner_read_ok ? "true" : "false");\n'
        '    if (e->attached_owner_read_ok) printf("\\\"0x%" PRIx64 "\\\"", e->attached_owner); else printf("null");\n'
        '  }\n  putchar(\'}\');\n}')
    replace('  if (argc != 5 && argc != 7 && argc != 8) {','  if (argc != 5 && argc != 7 && argc != 8 && argc != 9) {')
    replace('  extended = argc == 8;','  extended = argc >= 8;\n  character_identity = argc == 9;\n  if (character_identity && strcmp(argv[8], "--character-identity")) return 2;')
    replace('    emit_chain(frame, &cache, libg);','    emit_chain(frame, &cache, libg);\n    if (character_identity) printf(",\\\"character_identity\\\":{\\\"schema\\\":1,\\\"build\\\":160402012}");')
    path=HERE/'live_sampler3.c'
    assert not path.exists()
    path.write_text(text)
    return path

if __name__=='__main__':
    print(build())
