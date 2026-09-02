// memwrite <pid> <hex addr> <hex bytes>: write raw bytes into /proc/<pid>/mem (root). Prints the old bytes.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
int main(int argc, char** argv) {
  if (argc != 4) { fprintf(stderr, "usage: memwrite pid addr_hex bytes_hex\n"); return 2; }
  char path[64]; snprintf(path, sizeof path, "/proc/%s/mem", argv[1]);
  uint64_t addr = strtoull(argv[2], 0, 16);
  size_t n = strlen(argv[3]) / 2; unsigned char buf[256], old[256];
  if (n == 0 || n > sizeof buf) { fprintf(stderr, "bad length\n"); return 2; }
  for (size_t i = 0; i < n; ++i) { unsigned v; sscanf(argv[3] + 2 * i, "%2x", &v); buf[i] = (unsigned char)v; }
  int fd = open(path, O_RDWR); if (fd < 0) { perror("open mem"); return 1; }
  if (pread(fd, old, n, (off_t)addr) != (ssize_t)n) { perror("pread"); return 1; }
  if (pwrite(fd, buf, n, (off_t)addr) != (ssize_t)n) { perror("pwrite"); return 1; }
  printf("old:"); for (size_t i = 0; i < n; ++i) printf("%02x", old[i]); printf("\n");
  return 0;
}
