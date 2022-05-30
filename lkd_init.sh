#!/usr/bin/env bash

PATH_SSH_CONF=/home/kali/.ssh/config
PATH_SSH_KEY=/home/kali/.ssh/id_rsa
PROJECT=$(basename $(pwd))
COMMIT=e783362eb54cd99b2cac8b3a9aeac942e6f6ac07

# make sure we have it later so nothing times out
sudo true || exit 1

# build image for debugger container
docker build -f lkd_Dockerfile -t lkd-$PROJECT . || exit 1

# get sources for an in-tree build of kernel
wget https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/snapshot/linux-$COMMIT.tar.gz && \
tar xf linux-$COMMIT.tar.gz && \
rsync -a linux-$COMMIT/ $(pwd)/  && \
rm -rf linux-$COMMIT* || exit 1

# configure & build kernel, create debian image
./lkd_build_kernel.sh && \
sudo ./lkd_create_root_fs.sh || exit 1

# add entry to ssh config
if [[ -z $(grep -E "^Host lkd_qemu$" ${PATH_SSH_CONF}) ]]
then
  echo -en "\nHost lkd_qemu\n\tHostName localhost\n\tPort 2222\n\tUser root\n\tIdentityFile ${PATH_SSH_KEY}\n\tStrictHostKeyChecking false" >> ${PATH_SSH_CONF} || exit 1
fi

# fix broken symlink
ln -sf /project/scripts/gdb/vmlinux-gdb.py vmlinux-gdb.py

# create dockerignore
ls -a | grep -v lkd  | grep -v -E "^(.|..)$" > .dockerignore && \
echo "lkd_qemu_image.qcow2" >> .dockerignore || exit 1

# create gitignore
cp .dockerignore .gitignore && \
echo -e ".dockerignore\nlkd_vm.log\nfs/\nmm/" >> .gitignore || exit 1

exit 0
