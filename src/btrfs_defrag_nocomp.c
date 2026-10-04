// SPDX-License-Identifier: GPL-2.0
/* Issue NOCOMPRESS requests without userspace range/error translation. */
#include <errno.h>
#include <fcntl.h>
#include <linux/btrfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#ifndef BTRFS_DEFRAG_RANGE_NOCOMPRESS
#define BTRFS_DEFRAG_RANGE_NOCOMPRESS (1ULL << 3)
#endif

static unsigned long long number(const char *s)
{
	char *end;
	unsigned long long value;

	errno = 0;
	value = strtoull(s, &end, 0);
	if (errno || *end || end == s || *s == '-') {
		fprintf(stderr, "invalid number: %s\n", s);
		exit(2);
	}
	return value;
}

int main(int argc, char **argv)
{
	struct btrfs_ioctl_defrag_range_args range = { 0 };
	int fd, err = 0;
	const char *result;

	if (argc != 4) {
		fprintf(stderr, "usage: %s file start len\n", argv[0]);
		return 2;
	}
	range.flags = BTRFS_DEFRAG_RANGE_NOCOMPRESS;
	range.start = number(argv[2]);
	range.len = number(argv[3]);
	fd = open(argv[1], O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		perror("open");
		return 2;
	}
	if (ioctl(fd, BTRFS_IOC_DEFRAG_RANGE, &range) < 0)
		err = errno;
	close(fd);
	switch (err) {
	case 0: result = "OK"; break;
	case EINVAL: result = "EINVAL"; break;
	case EOPNOTSUPP: result = "EOPNOTSUPP"; break;
	case ENOTTY: result = "ENOTTY"; break;
	default:
		fprintf(stderr, "unexpected errno %d (%s)\n", err, strerror(err));
		return 1;
	}
	puts(result);
	return 0;
}
