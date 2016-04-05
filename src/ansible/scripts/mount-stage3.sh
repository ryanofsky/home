#!/bin/bash

set -x
set -e

STAGE3=http://gentoo.mirrors.easynews.com/linux/gentoo/releases/amd64/autobuilds/current-stage3-amd64-hardened/stage3-amd64-hardened-20160331.tar.bz2
BOOT=/dev/xvda
SWAP=/dev/xvdb
ROOT=/dev/xvdc

# So prompts don't hang the script forever. Ansible is fucking stupid.
exec < /dev/null

# Cleanup resumed.
umount -R /mnt/root || true
rmdir /mnt/root || true
cryptsetup close root || true
swapoff /dev/mapper/swap || true
cryptsetup close swap || true

# Format filesystems
yes | mke2fs "$BOOT"
cryptsetup -d /dev/urandom create swap "$SWAP"
mkswap /dev/mapper/swap
swapon /dev/mapper/swap
cryptsetup --verbose --batch-mode luksFormat "$ROOT" <<<"$LUKSPASS"
cryptsetup --verbose --batch-mode open --type luks "$ROOT" root <<<"$LUKSPASS"
mkfs.btrfs /dev/mapper/root

# Mount root filesystem.
mkdir /mnt/root
mount -o noatime /dev/mapper/root /mnt/root
btrfs su create /mnt/root/root
btrfs su create /mnt/root/portage

# Extract stage3
cd /tmp
test -e "${STAGE3##*/}" || wget "$STAGE3"
tar xjpf "${STAGE3##*/}" -C /mnt/root/root

# Create snapshot post-stage3.
mkdir /mnt/root/.snapshots
sdate() { date -u +"%Y%m%dT%H%M%SZ"; }
btrfs su snapshot -r /mnt/root/root /mnt/root/.snapshots/root@$(sdate)

# Mount other mounts.
mkdir /mnt/root/root/usr/portage
mount --bind /mnt/root/portage /mnt/root/root/usr/portage
mount -o noatime "$BOOT" /mnt/root/root/boot
