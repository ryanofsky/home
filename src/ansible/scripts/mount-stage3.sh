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

# Set up LUKS.
if [ "$WIPE" = yes ]; then
    cryptsetup --verbose --batch-mode luksFormat "$ROOT_DEV" <<<"$LUKS_PASS"
fi
cryptsetup --verbose --batch-mode open --type luks "$ROOT_DEV" root <<<"$LUKS_PASS"
cryptsetup -d /dev/urandom create swap "$SWAP_DEV"

# Set up filesystems.
if [ "$WIPE" = yes ]; then
    mkfs.btrfs /dev/mapper/root
    mkswap /dev/mapper/swap
    yes | mke2fs "$BOOT_DEV"
fi
mkdir /mnt/root
mount -o noatime /dev/mapper/root /mnt/root

# Populate root filesystem.
if [ "$WIPE" = yes ]; then
    btrfs su create /mnt/root/root
    btrfs su create /mnt/root/portage

    # Extract stage3.
    cd /tmp
    if ! [ -e "${STAGE3_URL##*/}" ]; then
        wget --no-check-certificate "$STAGE3_URL"
        wget --no-check-certificate "$STAGE3_URL.DIGESTS.asc"
    fi
    gpg --verify "${STAGE3_URL##*/}.DIGESTS.asc"
    grep $(sha512sum "${STAGE3_URL##*/}") <(gpg --decrypt "${STAGE3_URL##*/}.DIGESTS.asc")
    tar xjpf "${STAGE3_URL##*/}" --xattrs -C /mnt/root/root

    # Create snapshot post-stage3.
    mkdir /mnt/root/.snapshots
    sdate() { date -u +"%Y%m%dT%H%M%SZ"; }
    btrfs su snapshot -r /mnt/root/root /mnt/root/.snapshots/root@$(sdate)

    mkdir /mnt/root/root/usr/portage
fi

# Set up runtime.
swapon /dev/mapper/swap
mount --bind /mnt/root/portage /mnt/root/root/usr/portage
mount -o noatime "$BOOT_DEV" /mnt/root/root/boot
mount -t proc proc /mnt/gentoo/proc
mount --rbind /sys /mnt/gentoo/sys
mount --make-rslave /mnt/gentoo/sys
if [ -L /dev/shm ]; then
    mount -t tmpfs -o nosuid,nodev,noexec shm /dev/shm
    chmod 1777 /dev/shm
fi
mount --rbind /dev /mnt/gentoo/dev
mount --make-rslave /mnt/gentoo/dev
mount --rbind /tmp /mnt/root/root/tmp
cp -Lnv /etc/resolv.conf /mnt/root/root/etc/resolv.conf
mkdir /mnt/gentoo
mount --rbind /mnt/root/root /mnt/gentoo
