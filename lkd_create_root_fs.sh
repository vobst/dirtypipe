#!/usr/bin/env bash

# path/to/your/ssh_pubkey
PATH_SSH=/home/kali/.ssh/id_rsa.pub

if [ "$EUID" -ne 0 ]
then
  echo "Please run as root"
  exit 1
fi

IMG=lkd_qemu_image.qcow2
DIR=mount-point.dir

ROOT_PASSWD_HASH=$(openssl passwd -1 test) && \
qemu-img create $IMG 5g && \
mkfs.ext2 $IMG && \
mkdir $DIR && \
mount -o loop $IMG $DIR && \
debootstrap --arch amd64 \
--include=build-essential,vim,openssh-server,make \
bullseye $DIR && \
sed -i -e "s#root:\*#root:${ROOT_PASSWD_HASH}#" $DIR/etc/shadow && \
echo "lkd-debian-qemu" > $DIR/etc/hostname && \
echo -e "auto enp0s3\niface enp0s3 inet dhcp" >> $DIR/etc/network/interfaces && \
mkdir $DIR/root/.ssh && \
cat $PATH_SSH > $DIR/root/.ssh/authorized_keys && \
cp lkd_sshd_config $DIR/etc/ssh/ && \
cp lkd_dirtypipe_files.dir/poc.c $DIR/root && \
cp lkd_dirtypipe_files.dir/Makefile $DIR/root && \
cp lkd_dirtypipe_files.dir/prepare.sh $DIR/root && \
chmod 777 $DIR/root/prepare.sh && \
umount $DIR && \
rmdir $DIR && chmod 777 $IMG && exit 0 || \
umount $DIR && rmdir $DIR && exit 1

exit 1
