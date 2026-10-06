/* Public character-data identity from the already witnessed live layout.
 * The callback must return 1 only when every requested byte was read. No game
 * functions are called, and no address or name is cached between invocations.
 * An optional +0x180 pointer is raw diagnostic evidence; it confers no body,
 * attachment, ownership, or deduplication semantics by itself.
 */
#ifndef READER_CHARACTER_NAME_H
#define READER_CHARACTER_NAME_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define READER_CHARACTER_NAME_CAPACITY 129

typedef int (*reader_character_read_fn)(void *context, uint64_t address,
                                        void *output, size_t size);

typedef enum {
    READER_CHARACTER_OK = 0,
    READER_CHARACTER_READ_ERROR = 1,
    READER_CHARACTER_INVALID_POINTER = 2,
    READER_CHARACTER_INVALID_NAME = 3
} reader_character_status;

static inline uint32_t reader_character_u32le(const unsigned char *bytes) {
    return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) |
           ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
}

static inline uint64_t reader_character_u64le(const unsigned char *bytes) {
    return (uint64_t)reader_character_u32le(bytes) |
           ((uint64_t)reader_character_u32le(bytes + 4) << 32);
}

/* Validate the entire read range, including its final byte. */
static inline int reader_character_range(uint64_t base, uint64_t offset, size_t size,
                                  uint64_t *address) {
    uint64_t start;
    if (!base || !size || offset > UINT64_MAX - base) return 0;
    start = base + offset;
    if ((uint64_t)(size - 1) > UINT64_MAX - start) return 0;
    *address = start;
    return 1;
}

static inline const char *reader_character_status_name(reader_character_status status) {
    switch (status) {
        case READER_CHARACTER_OK: return "ok";
        case READER_CHARACTER_READ_ERROR: return "read_error";
        case READER_CHARACTER_INVALID_POINTER: return "invalid_pointer";
        case READER_CHARACTER_INVALID_NAME: return "invalid_name";
        default: return "invalid_status";
    }
}

/* out_name must have READER_CHARACTER_NAME_CAPACITY bytes. It is empty on every
 * failure. owner and owner_read_ok may each be NULL. A zero owner with read_ok=1
 * records a successfully read null pointer. An unavailable or overflowing owner
 * read leaves read_ok=0 and does not invalidate an otherwise decoded name.
 */
static inline reader_character_status reader_character_name(
    reader_character_read_fn read_bytes, void *context, uint64_t object_address,
    char out_name[READER_CHARACTER_NAME_CAPACITY], uint64_t *owner,
    int *owner_read_ok) {
    unsigned char raw[8];
    unsigned char name[128];
    uint64_t address, data_address, chars_address;
    uint32_t length;
    size_t i;

    if (out_name) memset(out_name, 0, READER_CHARACTER_NAME_CAPACITY);
    if (owner) *owner = 0;
    if (owner_read_ok) *owner_read_ok = 0;
    if (!out_name || !read_bytes) return READER_CHARACTER_READ_ERROR;

    if ((owner || owner_read_ok) &&
        reader_character_range(object_address, UINT64_C(0x180), 8, &address) &&
        read_bytes(context, address, raw, 8) == 1) {
        if (owner) *owner = reader_character_u64le(raw);
        if (owner_read_ok) *owner_read_ok = 1;
    }

    if (!reader_character_range(object_address, UINT64_C(0x48), 8, &address))
        return READER_CHARACTER_INVALID_POINTER;
    if (read_bytes(context, address, raw, 8) != 1)
        return READER_CHARACTER_READ_ERROR;
    data_address = reader_character_u64le(raw);

    if (!reader_character_range(data_address, UINT64_C(0x2c), 4, &address))
        return READER_CHARACTER_INVALID_POINTER;
    if (read_bytes(context, address, raw, 4) != 1)
        return READER_CHARACTER_READ_ERROR;
    length = reader_character_u32le(raw);
    /* Negative native int32 lengths also fail this unsigned upper bound. */
    if (length == 0 || length > 128) return READER_CHARACTER_INVALID_NAME;

    if (length < 8) {
        if (!reader_character_range(data_address, UINT64_C(0x30), length,
                                    &chars_address))
            return READER_CHARACTER_INVALID_POINTER;
    } else {
        if (!reader_character_range(data_address, UINT64_C(0x30), 8, &address))
            return READER_CHARACTER_INVALID_POINTER;
        if (read_bytes(context, address, raw, 8) != 1)
            return READER_CHARACTER_READ_ERROR;
        if (!reader_character_range(reader_character_u64le(raw), 0, length,
                                    &chars_address))
            return READER_CHARACTER_INVALID_POINTER;
    }
    if (read_bytes(context, chars_address, name, length) != 1)
        return READER_CHARACTER_READ_ERROR;
    for (i = 0; i < length; ++i) {
        unsigned char c = name[i];
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
              (c >= '0' && c <= '9') || c == '_'))
            return READER_CHARACTER_INVALID_NAME;
    }
    memcpy(out_name, name, length);
    out_name[length] = '\0';
    return READER_CHARACTER_OK;
}

#endif
