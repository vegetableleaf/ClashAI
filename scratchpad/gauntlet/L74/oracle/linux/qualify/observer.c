/* External observer. Never links, loads, calls or writes the game's module.
 * Wire protocol: ASCII command line -> signed decimal byte length + LF + bytes.
 * All target descriptors are O_RDONLY. No debugger attach or process stop.
 */
#if !defined(ORACLE_READ_ONLY) || ORACLE_READ_ONLY != 1
#error Build only with ORACLE_READ_ONLY
#endif
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { LIMIT = 1048576, READ_LIMIT = 65536 };
static unsigned char data[LIMIT];
static void reply(ssize_t n) {
    printf("%zd\n", n);
    if (n > 0 && fwrite(data, 1, (size_t)n, stdout) != (size_t)n) exit(1);
    fflush(stdout);
}
static void file_reply(const char *path) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) { reply(-errno); return; }
    size_t used = 0;
    while (used < LIMIT) {
        ssize_t n = read(fd, data + used, LIMIT - used);
        if (n < 0) { int e = errno; close(fd); reply(-e); return; }
        if (!n) break;
        used += (size_t)n;
    }
    close(fd);
    if (used == LIMIT) reply(-EOVERFLOW); else reply((ssize_t)used);
}
int main(int argc, char **argv) {
    if (argc != 2) return 64;
    char *end;
    long pid = strtol(argv[1], &end, 10);
    if (*end || pid <= 1 || pid > 2147483647L) return 64;
    char path[96], line[160], extra;
    snprintf(path, sizeof(path), "/proc/%ld/mem", pid);
    int mem = open(path, O_RDONLY | O_CLOEXEC);
    /* Read denial is terminal. No ptrace, policy changes or fallback. */
    if (mem < 0) { reply(-errno); return 77; }
    while (fgets(line, sizeof(line), stdin)) {
        uint64_t address; unsigned length;
        if (!strcmp(line, "maps\n") || !strcmp(line, "stat\n") || !strcmp(line, "cmdline\n")) {
            line[strcspn(line, "\n")] = 0;
            snprintf(path, sizeof(path), "/proc/%ld/%s", pid, line);
            file_reply(path);
        } else if (sscanf(line, "read %" SCNu64 " %u %c", &address, &length, &extra) == 2
                   && length > 0 && length <= READ_LIMIT && address <= (uint64_t)INT64_MAX - length) {
            ssize_t n = pread(mem, data, length, (off_t)address);
            reply(n < 0 ? -errno : n);
        } else {
            reply(-EINVAL);
            break;
        }
    }
    close(mem);
    return 0;
}
