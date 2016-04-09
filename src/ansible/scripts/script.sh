#!/bin/bash

mount-stage3() {
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
        btrfs su snapshot -r /mnt/root/root /mnt/root/.snapshots/root@$(sdate)

        mkdir /mnt/root/root/usr/portage
    fi

    # Set up runtime.
    mkswap /dev/mapper/swap
    swapon /dev/mapper/swap
    mount --bind /mnt/root/portage /mnt/root/root/usr/portage
    mount -o noatime "$BOOT_DEV" /mnt/root/root/boot
    mount -t proc proc /mnt/root/root/proc
    mount --rbind /sys /mnt/root/root/sys
    mount --make-rslave /mnt/root/root/sys
    if [ -L /dev/shm ]; then
        rm /dev/shm
        mkdir /dev/shm
        mount -t tmpfs -o nosuid,nodev,noexec shm /dev/shm
        chmod 1777 /dev/shm
    fi
    mount --rbind /dev /mnt/root/root/dev
    mount --make-rslave /mnt/root/root/dev
    mount --rbind /tmp /mnt/root/root/tmp
    rm -fv /mnt/root/root/etc/resolv.conf
    cp -Lnv /etc/resolv.conf /mnt/root/root/etc/resolv.conf
    mkdir /mnt/gentoo
    mount --rbind /mnt/root/root /mnt/gentoo
}

emerge() {
    # Update system
    emerge-webrsync
    USE="-systemd -udev" emerge -q1 sys-apps/util-linux sys-fs/lvm2 sys-fs/cryptsetup
    emerge -q --update --newuse --deep --with-bdeps=y @world
    emerge -q --depclean
    gcc-config 1
    . /etc/profile
    emerge -qe --update --newuse --deep --with-bdeps=y @world

    # Add needed packages.
    emerge -qn sys-kernel/hardened-sources app-editors/vim sys-kernel/dracut sys-fs/btrfs-progs sys-boot/grub app-portage/gentoolkit app-portage/eix app-portage/genlop sys-apps/gptfdisk app-misc/screen

    # Set timezone.
    emerge --config sys-libs/timezone-data

    # Set up locales.
    locale-gen
    eselect locale set en_US.utf8

    # Set up networking.
    systemctl enable systemd-networkd.service
    ln -snf /run/systemd/resolve/resolv.conf /etc/resolv.conf

    # Set up ssh.
    systemctl enable sshd
    mkdir /root/.ssh
    chmod 700 /root/.ssh
    cat >> /root/.ssh/authorized_keys <<EOF
ssh-rsa XXX
EOF
    chmod 600 /root/.ssh/authorized_keys
}

make-kernel() {
    . /etc/profile
    if ! mountpoint -q /boot; then
        mount /boot
    fi
    cd /usr/src/linux
    make defconfig
    kconfig
    make olddefconfig
    cp .config .config-normalized
    kconfig
    diff -u .config-normalized .config || true
    rm .config-normalized
    make
    make modules_install
    make install
    V=$(<include/config/kernel.release)
    dracut -a crypt --force /boot/initramfs-$V.img $V

    ROOT_DEV=$(findmnt -vno source /)
    ROOT_DEV_UUID=$(blkid -s UUID -o value $ROOT_DEV)
    # Needed otherwise /etc/grub.d/10_linux ignores GRUB_DEVICE_UUID
    if [ ! -e /dev/disk/by-uuid/"$ROOT_DEV_UUID" ]; then
        ln -snv $ROOT_DEV /dev/disk/by-uuid/"$ROOT_DEV_UUID"
    fi

    mkdir -p /boot/grub
    grub2-mkconfig -o /boot/grub/grub.cfg
    grub2-install -v "$BOOT_MBR_DEV"
}

kconfig() {
    # Support for /proc/config.gz, fanotify, virtual networking/filesystems
    scripts/config \
      -m IKCONFIG \
      -e IKCONFIG_PROC \
      -e FANOTIFY \
      -m BRIDGE \
      -m VETH \
      -m MACVLAN \
      -m VLAN_8021Q \
      -m TUN \
      -m FSCACHE \
      -m CACHEFILES \
      -e FANOTIFY \
      -m FUSE_FS \
      -m CUSE \
      -m OVERLAY_FS \
      -m 9P_FS \
      -e 9P_FSCACHE \
      -e 9P_FS_POSIX_ACL \
      -e 9P_FS_SECURITY \
      -m NET_9P \
      -m NET_9P_VIRTIO \
      -m CIFS \
      -e CIFS_XATTR

    # Docker options https://github.com/docker/docker/blob/master/contrib/check-config.sh
    scripts/config \
      -e NAMESPACES \
      -e NET_NS \
      -e PID_NS \
      -e IPC_NS \
      -e UTS_NS \
      -e DEVPTS_MULTIPLE_INSTANCES \
      -e CGROUPS \
      -e CGROUP_CPUACCT \
      -e CGROUP_DEVICE \
      -e CGROUP_FREEZER \
      -e CGROUP_SCHED \
      -e CPUSETS \
      -e MEMCG \
      -e KEYS \
      -m MACVLAN \
      -m VETH \
      -m BRIDGE \
      -e NETFILTER_ADVANCED \
      -m BRIDGE_NETFILTER \
      -m NF_NAT_IPV4 \
      -m IP_NF_FILTER \
      -m IP_NF_TARGET_MASQUERADE \
      -m NETFILTER_XT_MATCH_ADDRTYPE \
      -m NETFILTER_XT_MATCH_CONNTRACK \
      -m NF_NAT \
      -e NF_NAT_NEEDED \
      -e POSIX_MQUEUE \
      -e USER_NS \
      -e SECCOMP \
      -e CGROUP_PIDS \
      -e MEMCG_KMEM \
      -e MEMCG_SWAP \
      -e MEMCG_SWAP_ENABLED \
      -e CGROUP_NET_PRIO \
      -e BLK_CGROUP \
      -m IOSCHED_CFQ \
      -e BLK_DEV_THROTTLING \
      -e CGROUP_PERF \
      -e CGROUP_HUGETLB \
      -m NET_CLS_CGROUP \
      -e CGROUP_NET_PRIO \
      -e CFS_BANDWIDTH \
      -e FAIR_GROUP_SCHED \
      -e RT_GROUP_SCHED \
      -m EXT4_FS \
      -e EXT4_FS_POSIX_ACL \
      -e EXT4_FS_SECURITY \
      -m BTRFS_FS \
      -m BLK_DEV_DM \
      -m DM_THIN_PROVISIONING \
      -m OVERLAY_FS

    # lxc-checkpoint options
    scripts/config \
      -e EXPERT \
      -m CHECKPOINT_RESTORE \
      -m UNIX_DIAG \
      -m INET_DIAG \
      -m INET_UDP_DIAG \
      -m PACKET_DIAG \
      -m NETLINK_DIAG

    # KVM options http://www.linux-kvm.org/page/Tuning_Kernel
    scripts/config \
      -e VIRTUALIZATION \
      -m KVM \
      -m KVM_INTEL \
      -m VHOST_NET \
      -e HIGH_RES_TIMERS \
      -e HPET \
      -e COMPACTION \
      -e MIGRATION \
      -e KSM \
      -e TRANSPARENT_HUGEPAGE \
      -e CGROUPS \
      -m VIRTIO \
      -m VIRTIO_PCI \
      -m VIRTIO_BALLOON \
      -m VIRTIO_NET \
      -m VIRTIO_BLK \
      -m VIRTIO_PCI \
      -m VIRTIO_BALLOON \
      -m VIRTIO_CONSOLE \
      -m HW_RANDOM_VIRTIO \
      -e PCI_MSI \
      -e KVM_GUEST \
      -e PARAVIRT \
      -e PARAVIRT_CLOCK \
      -e MEMORY_HOTPLUG \
      -e MEMORY_HOTREMOVE \
      -e ACPI_HOTPLUG_MEMORY \
      -e HOTPLUG_PCI \
      -e HYPERVISOR_GUEST

    # Support for KVM
    # https://www.linode.com/docs/platform/kvm-reference
    scripts/config \
      -e KVM_GUEST \
      -e VIRTIO \
      -e VIRTIO_PCI \
      -e VIRTIO_PCI_LEGACY \
      -e SCSI_LOWLEVEL \
      -e SCSI_VIRTIO \
      -m VIRTIO_NET \
      -e SERIAL_8250 \
      -e SERIAL_8250_CONSOLE

    # http://wiki.gentoo.org/wiki/DM-Crypt_LUKS
    # Support for luks crypt. luksDump output:
    #    Cipher name:    aes
    #    Cipher mode:    xts-plain64
    #    Hash spec:      sha1
    scripts/config \
      -e BLK_DEV_DM \
      -e DM_CRYPT \
      -e CRYPTO_AES \
      -e CRYPTO_SHA256 \
      -e CRYPTO_XTS

    # BTRFS
    scripts/config \
      -e BTRFS_FS \
      -e BTRFS_FS_POSIX_ACL \
      -d BTRFS_FS_CHECK_INTEGRITY \
      -d BTRFS_FS_RUN_SANITY_TESTS \
      -d BTRFS_DEBUG \
      -d BTRFS_ASSERT

    # Systemd required https://github.com/systemd/systemd/blob/master/README
    scripts/config \
      -e DEVTMPFS \
      -e CGROUPS \
      -e INOTIFY_USER \
      -e SIGNALFD \
      -e TIMERFD \
      -e EPOLL \
      -e NET \
      -e SYSFS \
      -e PROC_FS \
      -e FHANDLE \
      -d SYSFS_DEPRECATED \
      --set-str UEVENT_HELPER_PATH "" \
      -d FW_LOADER_USER_HELPER \
      -e DMIID \
      -e BLK_DEV_BSG \
      -e NET_NS \
      -e DEVPTS_MULTIPLE_INSTANCES

    # Systemd optional https://github.com/systemd/systemd/blob/master/README
    # Symbol: CONFIG_UEVENT_HELPER_PATH=""
    # - Due to messy bug
    #   - https://bugzilla.redhat.com/show_bug.cgi?id=979695
    #   - https://bugs.gentoo.org/show_bug.cgi?id=493874
    #   - https://bugzilla.redhat.com/show_bug.cgi?id=759402#c75
    #   - Otherwise hangs waiting for swap partition to be ready.
    #     - kobject_uevent_env returns error if call_usermodehelper fails
    #     - this causes libdevmapper to cancel udev fallback and call mknod(/dev/mapper/swap)
    #       - (this is supposedly configurable with DM_UDEV_DISABLE_LIBRARY_FALLBACK)
    #     - because udev cancel and a node exists rather than a symlink inotify never triggers, udev waits forever
    #   - More
    #     - search ["SYSTEMD_READY" swap]
    #     - https://bugzilla.redhat.com/show_bug.cgi?id=711394
    #   - Confirm value
    #     cat /proc/sys/kernel/hotplug
    #     cat /sys/kernel/uevent_helper
    #
    # Symbol: CONFIG_FW_LOADER_USER_HELPER=n
    # - bad according to systemd readme
    scripts/config \
      -e IPV6 \
      -e AUTOFS4_FS \
      -e TMPFS \
      -e TMPFS_XATTR \
      -e TMPFS_POSIX_ACL \
      -e SECCOMP \
      -e PROC_CHILDREN \
      -e EXPERT \
      -e CHECKPOINT_RESTORE \
      -e CGROUP_SCHED \
      -e FAIR_GROUP_SCHED \
      -e CFS_BANDWIDTH \
      -e RT_GROUP_SCHED \
      -d AUDIT
}

sdate() {
    date -u +"%Y%m%dT%H%M%SZ";
}

if [ -n "$CHROOT" ]; then
    chroot="$CHROOT"
    unset CHROOT
    exec chroot "$chroot" /bin/bash -c "$(<$0)" "$0" "$@"
fi

# So prompts don't hang the script forever. Ansible is fucking stupid.
exec < /dev/null

FUN="$1"
shift

set -e
set -x
"$FUN" "$@"
