// memdump <pid> <hex start> <hex len> <out>: copy a range of /proc/<pid>/mem to a file (root).
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
int main(int argc, char** argv) {
  if (argc != 5) { fprintf(stderr, "usage: memdump pid start_hex len_hex out\n"); return 2; }
  char path[64]; snprintf(path, sizeof path, "/proc/%s/mem", argv[1]);
  uint64_t start = strtoull(argv[2], 0, 16), len = strtoull(argv[3], 0, 16);
  int fd = open(path, O_RDONLY); if (fd < 0) { perror("open mem"); return 1; }
  int out = open(argv[4], O_WRONLY | O_CREAT | O_TRUNC, 0666); if (out < 0) { perror("open out"); return 1; }
  static char buf[1 << 20]; uint64_t done = 0;
  while (done < len) {
    size_t want = len - done > sizeof buf ? sizeof buf : (size_t)(len - done);
    ssize_t n = pread(fd, buf, want, (off_t)(start + done));
    if (n <= 0) { perror("pread"); fprintf(stderr, "at +0x%llx\n", (unsigned long long)done); break; }
    if (write(out, buf, (size_t)n) != n) { perror("write"); return 1; }
    done += (uint64_t)n;
  }
  printf("%s: %llu of %llu bytes\n", argv[4], (unsigned long long)done, (unsigned long long)len);
  return done == len ? 0 : 1;
}
