#!/bin/bash

set -x
set -e

# So prompts don't hang the script forever. Ansible is fucking stupid.
exec < /dev/null

# Clean up previous.
umount -R /mnt/gentoo || true
rmdir /mnt/gentoo || true
umount -R /mnt/root || true
rmdir /mnt/root || true
cryptsetup close root || true
swapoff /dev/mapper/swap || true
cryptsetup close swap || true

# Format filesystems.
yes | mke2fs "$BOOT_DEV"
cryptsetup -d /dev/urandom create swap "$SWAP_DEV"
mkswap /dev/mapper/swap
swapon /dev/mapper/swap
cryptsetup --verbose --batch-mode luksFormat "$ROOT_DEV" <<<"$LUKS_PASS"
cryptsetup --verbose --batch-mode open --type luks "$ROOT_DEV" root <<<"$LUKS_PASS"
mkfs.btrfs /dev/mapper/root

# Mount root filesystem.
mkdir /mnt/root
mount -o noatime /dev/mapper/root /mnt/root
btrfs su create /mnt/root/root
btrfs su create /mnt/root/portage

# Extract stage3.
cd /tmp
test -e "${STAGE3_URL##*/}" || wget "$STAGE3_URL"
tar xjpf "${STAGE3_URL##*/}" -C /mnt/root/root

# Create snapshot post-stage3.
mkdir /mnt/root/.snapshots
sdate() { date -u +"%Y%m%dT%H%M%SZ"; }
btrfs su snapshot -r /mnt/root/root /mnt/root/.snapshots/root@$(sdate)

# Set up /mnt/gentoo.
mkdir /mnt/root/root/usr/portage
mount --bind /mnt/root/portage /mnt/root/root/usr/portage
mount -o noatime "$BOOT_DEV" /mnt/root/root/boot
mkdir /mnt/gentoo
mount --rbind /mnt/root/root /mnt/gentoo
