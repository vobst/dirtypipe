#!/usr/bin/env bash

# build image for debugger container
docker build -f lkd_Dockerfile -t lkd . || exit 1

# get sources for an in-tree build of buggy kernel
# TOOD possible to decompress wo/ creating extra folder? shorten name?
wget https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/snapshot/linux-e783362eb54cd99b2cac8b3a9aeac942e6f6ac07.tar.gz && \
tar xf linux-e783362eb54cd99b2cac8b3a9aeac942e6f6ac07.tar.gz && \
rsync -a linux-e783362eb54cd99b2cac8b3a9aeac942e6f6ac07/ $(pwd)/  && \
rm -rf linux-e783362eb54cd99b2cac8b3a9aeac942e6f6ac07* || exit 1

./lkd_build_kernel.sh && \
./lkd_create_root_fs.sh || exit 1

# fix broken (for docker) symlink
ln -sf /project/scripts/gdb/vmlinux-gdb.py vmlinux-gdb.py

# create dockerignore
ls -a | grep -v lkd  | grep -v -E "^(.|..)$" > .dockerignore && \
echo "lkd_qemu_image.qcow2" >> .dockerignore || exit 1

exit 0
