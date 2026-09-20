// SPDX-License-Identifier: GPL-2.0
/* Exercise both defrag compression ABI layouts, including with old headers. */
#include <errno.h>
#include <fcntl.h>
#include <linux/btrfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#ifndef BTRFS_DEFRAG_RANGE_COMPRESS_LEVEL
#define BTRFS_DEFRAG_RANGE_COMPRESS_LEVEL 4
#endif

int main(int argc, char **argv)
{
	struct btrfs_ioctl_defrag_range_args args = { 0 };
	unsigned char *compression = (unsigned char *)&args.compress_type;
	char *end;
	long level;
	int fd, ret, error;

	if (argc != 3) {
		fprintf(stderr, "Usage: %s FILE legacy|LEVEL\n", argv[0]);
		return 1;
	}
	args.len = ~0ULL;
	args.flags = BTRFS_DEFRAG_RANGE_COMPRESS;
	if (!strcmp(argv[2], "legacy")) {
		args.compress_type = 3; /* BTRFS_COMPRESS_ZSTD */
	} else {
		errno = 0;
		level = strtol(argv[2], &end, 10);
		if (errno || end == argv[2] || *end || level < -15 || level > 15)
			return 1;
		args.flags |= BTRFS_DEFRAG_RANGE_COMPRESS_LEVEL;
		/* The new ABI is two bytes, independent of host endianness. */
		compression[0] = 3;
		compression[1] = (unsigned char)level;
	}
	fd = open(argv[1], O_RDWR);
	if (fd < 0) {
		perror("open");
		return 1;
	}
	ret = ioctl(fd, BTRFS_IOC_DEFRAG_RANGE, &args);
	error = errno;
	close(fd);
	if (ret < 0) {
		errno = error;
		perror("BTRFS_IOC_DEFRAG_RANGE");
		return error == EOPNOTSUPP ? 77 : 1;
	}
	return 0;
}
