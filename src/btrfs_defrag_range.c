// SPDX-License-Identifier: GPL-2.0
/* Raw Btrfs defrag ioctl exerciser.  Keep the ABI request separate from CLI. */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/btrfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#ifndef BTRFS_DEFRAG_RANGE_NOCOMPRESS
#define BTRFS_DEFRAG_RANGE_NOCOMPRESS 8
#endif
#ifndef BTRFS_DEFRAG_RANGE_COMPRESS_LEVEL
#define BTRFS_DEFRAG_RANGE_COMPRESS_LEVEL 4
#endif

static unsigned long long number(const char *s)
{
	char *end;
	unsigned long long value;
	errno = 0;
	value = strtoull(s, &end, 0);
	if (errno || *end || end == s) {
		fprintf(stderr, "invalid number: %s\n", s);
		exit(2);
	}
	return value;
}

int main(int argc, char **argv)
{
	struct btrfs_ioctl_defrag_range_args range = {0};
	unsigned long long flags, type;
	long level;
	char *end;
	int fd, err = 0;
	const char *name;

	if (argc != 7) {
		fprintf(stderr, "usage: %s file flags start len type level\n", argv[0]);
		return 2;
	}
	flags = number(argv[2]);
	type = number(argv[5]);
	errno = 0;
	level = strtol(argv[6], &end, 0);
	if (errno || *end || end == argv[6] || level < -128 || level > 127 ||
	    type > 255) {
		fprintf(stderr, "invalid type or level\n");
		return 2;
	}
	range.flags = flags;
	range.start = number(argv[3]);
	range.len = number(argv[4]);
	if (flags & BTRFS_DEFRAG_RANGE_COMPRESS_LEVEL) {
		/* The type/level pair overlays compress_type in the UAPI union.
		 * Build against older distro headers without changing the layout. */
		unsigned char *pair = (unsigned char *)&range.compress_type;
		pair[0] = type;
		pair[1] = (signed char)level;
	} else {
		range.compress_type = type;
	}
	fd = open(argv[1], O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		perror("open");
		return 2;
	}
	if (ioctl(fd, BTRFS_IOC_DEFRAG_RANGE, &range) < 0)
		err = errno;
	close(fd);
	switch (err) {
	case 0: name = "OK"; break;
	case EINVAL: name = "EINVAL"; break;
	case EOPNOTSUPP: name = "EOPNOTSUPP"; break;
	case ENOTTY: name = "ENOTTY"; break;
	case EROFS: name = "EROFS"; break;
	case ENOSPC: name = "ENOSPC"; break;
	default:
		fprintf(stderr, "unexpected errno %d (%s)\n", err, strerror(err));
		return 1;
	}
	puts(name);
	return 0;
}
