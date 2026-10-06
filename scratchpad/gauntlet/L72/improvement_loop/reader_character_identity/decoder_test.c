/* Offline decoder harness. It never reads a device or process address space.
 * stdin contains consecutive little-endian batches until clean EOF:
 *   uint32 nblocks;
 *   nblocks * (uint64 address, uint32 length, length raw bytes);
 *   uint32 nobjects; nobjects * uint64 object_address.
 * A callback read must fit wholly within one captured block. Among duplicate
 * or overlapping blocks, the last exact-start block with sufficient bytes wins;
 * otherwise the last containing block wins. No bytes cross batch boundaries.
 */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#include "character_name.h"

#define MAX_BLOCKS UINT32_C(4096)
#define MAX_BLOCK_BYTES UINT32_C(1048576)
#define MAX_BATCH_BYTES UINT64_C(67108864)
#define MAX_OBJECTS UINT32_C(4096)

typedef struct {
    uint64_t address;
    uint32_t length;
    unsigned char *bytes;
} captured_block;

typedef struct {
    uint32_t count;
    captured_block *blocks;
} captured_batch;

static int captured_read(void *context, uint64_t address, void *output,
                         size_t size) {
    captured_batch *batch = (captured_batch *)context;
    size_t i;
    if (!size || (uint64_t)(size - 1) > UINT64_MAX - address) return 0;
    for (i = batch->count; i > 0; --i) {
        const captured_block *block = &batch->blocks[i - 1];
        if (block->address == address && size <= block->length) {
            memcpy(output, block->bytes, size);
            return 1;
        }
    }
    for (i = batch->count; i > 0; --i) {
        const captured_block *block = &batch->blocks[i - 1];
        if (address >= block->address &&
            address - block->address <= block->length &&
            size <= (uint64_t)block->length - (address - block->address)) {
            memcpy(output, block->bytes + (size_t)(address - block->address), size);
            return 1;
        }
    }
    return 0;
}

static int input_exact(void *output, size_t size) {
    return fread(output, 1, size, stdin) == size;
}

static int input_u32(uint32_t *value) {
    unsigned char bytes[4];
    if (!input_exact(bytes, sizeof(bytes))) return 0;
    *value = reader_character_u32le(bytes);
    return 1;
}

static int input_u64(uint64_t *value) {
    unsigned char bytes[8];
    if (!input_exact(bytes, sizeof(bytes))) return 0;
    *value = reader_character_u64le(bytes);
    return 1;
}

static void free_batch(captured_batch *batch) {
    uint32_t i;
    for (i = 0; i < batch->count; ++i) free(batch->blocks[i].bytes);
    free(batch->blocks);
    batch->blocks = NULL;
    batch->count = 0;
}

int main(void) {
    uint64_t batch_index = 0;
    for (;;) {
        unsigned char count_bytes[4];
        size_t count_read = fread(count_bytes, 1, sizeof(count_bytes), stdin);
        captured_batch batch = {0, NULL};
        uint64_t total_bytes = 0;
        uint32_t nblocks, nobjects = 0, i;
        const char *error = NULL;

        if (count_read == 0 && feof(stdin) && !ferror(stdin))
            return ferror(stdout) ? 3 : 0;
        if (count_read != sizeof(count_bytes)) {
            fprintf(stderr, "Incomplete batch header at batch %" PRIu64 "\n", batch_index);
            return 2;
        }
        nblocks = reader_character_u32le(count_bytes);
        if (nblocks > MAX_BLOCKS) {
            fprintf(stderr, "Block count exceeds bound at batch %" PRIu64 "\n", batch_index);
            return 2;
        }
        if (nblocks) {
            batch.blocks = (captured_block *)calloc(nblocks, sizeof(captured_block));
            if (!batch.blocks) {
                fprintf(stderr, "Allocation failed at batch %" PRIu64 "\n", batch_index);
                return 2;
            }
        }
        batch.count = nblocks;
        for (i = 0; i < nblocks; ++i) {
            captured_block *block = &batch.blocks[i];
            if (!input_u64(&block->address) || !input_u32(&block->length)) {
                error = "Incomplete block header"; break;
            }
            if (!block->length || block->length > MAX_BLOCK_BYTES ||
                (uint64_t)(block->length - 1) > UINT64_MAX - block->address ||
                total_bytes + block->length > MAX_BATCH_BYTES) {
                error = "Invalid block range or budget"; break;
            }
            total_bytes += block->length;
            block->bytes = (unsigned char *)malloc(block->length);
            if (!block->bytes) { error = "Allocation failed"; break; }
            if (!input_exact(block->bytes, block->length)) {
                error = "Incomplete block bytes"; break;
            }
        }
        if (!error && !input_u32(&nobjects)) error = "Missing object count";
        if (!error && nobjects > MAX_OBJECTS) error = "Object count exceeds bound";
        for (i = 0; !error && i < nobjects; ++i) {
            uint64_t object_address, owner = 0;
            int owner_read_ok = 0;
            char name[READER_CHARACTER_NAME_CAPACITY];
            reader_character_status status;
            if (!input_u64(&object_address)) { error = "Incomplete object address"; break; }
            status = reader_character_name(captured_read, &batch, object_address,
                                           name, &owner, &owner_read_ok);
            printf("{\"batch_index\":%" PRIu64 ",\"address\":\"0x%" PRIx64
                   "\",\"native_name\":", batch_index, object_address);
            if (status == READER_CHARACTER_OK) printf("\"%s\"", name);
            else printf("null");
            printf(",\"status\":\"%s\",\"attached_owner\":",
                   reader_character_status_name(status));
            if (owner_read_ok && owner) printf("\"0x%" PRIx64 "\"", owner);
            else printf("null");
            printf(",\"attached_owner_read_ok\":%s}\n", owner_read_ok ? "true" : "false");
            if (ferror(stdout)) { error = "Output failure"; break; }
        }
        free_batch(&batch);
        if (error) {
            fprintf(stderr, "%s at batch %" PRIu64 "\n", error, batch_index);
            return 2;
        }
        ++batch_index;
    }
}
