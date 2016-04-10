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
    test -z "$SWAP_DEV" || cryptsetup -d /dev/urandom create swap "$SWAP_DEV"

    # Set up filesystems.
    if [ "$WIPE" = yes ]; then
        mkfs.btrfs /dev/mapper/root
        if [ -n "$BOOT_DEV" ]; then
            yes | mke2fs "$BOOT_DEV"
        fi
        if [ -n "$UEFI_DEV" ]; then
            mkfs.vfat -F32 "$UEFI_DEV"
        fi
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
        btrfs su snapshot -r /mnt/root/root /mnt/root/.snapshots/root@$(sdate).stage3

        mkdir /mnt/root/root/usr/portage
    fi

    # Set up runtime.
    if [ -n "$SWAP_DEV" ]; then
        mkswap /dev/mapper/swap
        swapon /dev/mapper/swap
    fi
    mount --bind /mnt/root/portage /mnt/root/root/usr/portage
    test -z "$BOOT_DEV" || mount -o noatime "$BOOT_DEV" /mnt/root/root/boot
    test -z "$UEFI_DEV" || mount "$UEFI_DEV" /mnt/root/root/boot
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

emerge-world() {
    # Update system
    #emerge-webrsync
    #USE="-systemd -udev" emerge -q1 sys-apps/util-linux sys-fs/lvm2 sys-fs/cryptsetup
    emerge -q --update --newuse --deep --with-bdeps=y @world
    emerge -q --depclean
    gcc-config 1
    . /etc/profile
    emerge -qe --update --newuse --deep --with-bdeps=y @world

    # Add needed packages.
    PKG="sys-kernel/hardened-sources app-editors/vim sys-kernel/dracut sys-fs/btrfs-progs app-portage/gentoolkit app-portage/eix app-portage/genlop sys-apps/gptfdisk app-misc/screen"
    if [ -n "$BOOT_DEV" ]; then
        PKG="$PKG sys-boot/grub"
    fi
    if [ -n "$UEFI_DEV" ]; then
        PKG="$PKG sys-boot/efibootmgr"
    fi
    emerge -qn $PKG

    # Set timezone.
    emerge --config sys-libs/timezone-data

    # Set up locales.
    locale-gen
    eselect locale set en_US.utf8

    # Set up networking.
    systemctl enable systemd-networkd.service
    systemctl enable systemd-resolved.service
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
    if [ "$INVENTORY_HOSTNAME" = think ]; then
        # lspci -k -nn
        # Host bridge [0600]: Intel Corporation 3rd Gen Core processor DRAM Controller [8086:0154] (rev 09)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: ivb_uncore
        scripts/config -e PERF_EVENTS_INTEL_UNCORE
        # VGA compatible controller [0300]: Intel Corporation 3rd Gen Core processor Graphics Controller [8086:0166] (rev 09)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: i915
        scripts/config -m DRM_I915 -e SND_HDA_I915
        # USB controller [0c03]: Intel Corporation 7 Series/C210 Series Chipset Family USB xHCI Host Controller [8086:1e31] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        scripts/config -m USB_XHCI_HCD
        # Communication controller [0780]: Intel Corporation 7 Series/C210 Series Chipset Family MEI Controller #1 [8086:1e3a] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        scripts/config -e WATCHDOG_CORE -m INTEL_MEI -m INTEL_MEI_ME
        # Serial controller [0700]: Intel Corporation 7 Series/C210 Series Chipset Family KT Controller [8086:1e3d] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: serial
        scripts/config -e SERIAL_8250 -e SERIAL_8250_CONSOLE
        # Ethernet controller [0200]: Intel Corporation 82579LM Gigabit Network Connection [8086:1502] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f3]
        # Kernel driver in use: e1000e
        # Kernel modules: e1000e
        scripts/config -m E1000E
        # USB controller [0c03]: Intel Corporation 7 Series/C210 Series Chipset Family USB Enhanced Host Controller #1 [8086:1e26] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: ehci-pci
        # USB controller [0c03]: Intel Corporation 7 Series/C210 Series Chipset Family USB Enhanced Host Controller #2 [8086:1e2d] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: ehci-pci
        scripts/config -e USB_EHCI_PCI
        # Audio device [0403]: Intel Corporation 7 Series/C210 Series Chipset Family High Definition Audio Controller [8086:1e20] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: snd_hda_intel
        scripts/config -m SND_HDA_INTEL
        # PCI bridge [0604]: Intel Corporation 7 Series/C210 Series Chipset Family PCI Express Root Port 1 [8086:1e10] (rev c4)
        # Kernel driver in use: pcieport
        # PCI bridge [0604]: Intel Corporation 7 Series/C210 Series Chipset Family PCI Express Root Port 2 [8086:1e12] (rev c4)
        # Kernel driver in use: pcieport
        # PCI bridge [0604]: Intel Corporation 7 Series/C210 Series Chipset Family PCI Express Root Port 3 [8086:1e14] (rev c4)
        # Kernel driver in use: pcieport
        scripts/config -e PCIEPORTBUS
        # ISA bridge [0601]: Intel Corporation QM77 Express Chipset LPC Controller [8086:1e55] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        scripts/config -m LPC_ICH
        # SATA controller [0106]: Intel Corporation 7 Series Chipset Family 6-port SATA Controller [AHCI mode] [8086:1e03] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: ahci
        scripts/config -e SATA_AHCI
        # SMBus [0c05]: Intel Corporation 7 Series/C210 Series Chipset Family SMBus Controller [8086:1e22] (rev 04)
        # Subsystem: Lenovo Device [17aa:21f6]
        # Kernel driver in use: i801_smbus
        scripts/config -m I2C_I801
        # System peripheral [0880]: Ricoh Co Ltd PCIe SDXC/MMC Host Controller [1180:e823] (rev 04)
        # Subsystem: Lenovo PCIe SDXC/MMC Host Controller [17aa:21f6]
        scripts/config -m MMC -m MMC_SDHCI -m MMC_SDHCI_PCI
        # Network controller [0280]: Intel Corporation Centrino Advanced-N 6205 [Taylor Peak] [8086:0085] (rev 34)
        # Subsystem: Intel Corporation Centrino Advanced-N 6205 AGN [8086:1311]
        # Kernel driver in use: iwlwifi
        # Kernel modules: iwlwifi
        scripts/config -m IWLWIFI -m IWLDVM

        # Documentation/laptops/thinkpad-acpi.txt
        scripts/config -m THINKPAD_ACPI -e THINKPAD_ACPI_ALSA_SUPPORT -e THINKPAD_ACPI_VIDEO -e SENSORS_HDAPS

        # lsusb -v
        #   idVendor           0x0a5c Broadcom Corp.
        #   idProduct          0x21e6 BCM20702 Bluetooth 4.0 [ThinkPad]
        #   bcdDevice            1.12
        #   iManufacturer           1 Broadcom Corp
        #   iProduct                2 BCM20702A0
        #   iSerial                 3 689423ED600F
        # http://www.thinkwiki.org/wiki/How_to_setup_Bluetooth
        # http://www.thinkwiki.org/wiki/Bluetooth_Daughter_Card_(14_pins)
        # https://download.lenovo.com/parts/ThinkPad/t530_fru_bom_20131007.pdf
        # https://wiki.gentoo.org/wiki/Bluetooth
        scripts/config -m BT -m BT_HCIBTUSB -m BT_RFCOMM -m BT_HIDP
        #   idVendor           0x04f2 Chicony Electronics Co., Ltd
        #   idProduct          0xb2ea Integrated Camera [ThinkPad]
        #   bcdDevice            5.18
        #   iManufacturer           1 Chicony Electronics Co., Ltd.
        #   iProduct                2 Integrated Camera
        #   iSerial                 0
        scripts/config -m MEDIA_SUPPORT -e MEDIA_USB_SUPPORT -e MEDIA_CAMERA_SUPPORT -m VIDEO_V4L2 -m USB_VIDEO_CLASS -e USB_VIDEO_CLASS_INPUT_EVDEV
        #   idVendor           0x147e Upek
        #   idProduct          0x2020 TouchChip Fingerprint Coprocessor (WBF advanced mode)
        #   bcdDevice            0.01
        #   iManufacturer           1 Auth
        #   iProduct                2 Biometric Coprocessor
        #   iSerial                 0
        # http://www.thinkwiki.org/wiki/Integrated_Fingerprint_Reader
        # https://wiki.archlinux.org/index.php/Fprint
        true

        # Sabrent USB audio adapter (from amazon 2015-08-29)
        scripts/config -m SND_USB_AUDIO
    fi

    if [ "$INVENTORY_HOSTNAME" = mini ]; then
        # lspci -k -nn
        # VGA compatible controller [0300]: Intel Corporation Haswell-ULT Integrated Graphics Controller [8086:0a06] (rev 0b)
        # DeviceName: Onboard IGD
        # Subsystem: Hewlett-Packard Company Haswell-ULT Integrated Graphics Controller [103c:2b38]
        # Kernel driver in use: i915
        # Kernel modules: i915
        scripts/config -m DRM_I915 -e SND_HDA_I915
        # Audio device [0403]: Intel Corporation Haswell-ULT HD Audio Controller [8086:0a0c] (rev 0b)
        # Subsystem: Hewlett-Packard Company Haswell-ULT HD Audio Controller [103c:2b38]
        scripts/config -m SND_HDA_INTEL
        # USB controller [0c03]: Intel Corporation 8 Series USB xHCI HC [8086:9c31] (rev 04)
        # Subsystem: Hewlett-Packard Company 8 Series USB xHCI HC [103c:2b38]
        # Kernel driver in use: xhci_hcd
        scripts/config -m USB_XHCI_HCD
        # Communication controller [0780]: Intel Corporation 8 Series HECI #0 [8086:9c3a] (rev 04)
        # Subsystem: Hewlett-Packard Company 8 Series HECI [103c:2b38]
        # Kernel driver in use: mei_me
        # Kernel modules: mei_me
        scripts/config -e WATCHDOG_CORE -m INTEL_MEI -m INTEL_MEI_ME
        # Audio device [0403]: Intel Corporation 8 Series HD Audio Controller [8086:9c20] (rev 04)
        # DeviceName: Onboard Audio
        # Subsystem: Hewlett-Packard Company 8 Series HD Audio Controller [103c:2b38]
        scripts/config -e SND_HDA_INTEL
        # PCI bridge [0604]: Intel Corporation 8 Series PCI Express Root Port 1 [8086:9c10] (rev e4)
        # Kernel driver in use: pcieport
        # Kernel modules: shpchp
        # PCI bridge [0604]: Intel Corporation 8 Series PCI Express Root Port 3 [8086:9c14] (rev e4)
        # Kernel driver in use: pcieport
        # Kernel modules: shpchp
        # PCI bridge [0604]: Intel Corporation 8 Series PCI Express Root Port 4 [8086:9c16] (rev e4)
        # Kernel driver in use: pcieport
        # Kernel modules: shpchp
        # PCI bridge [0604]: Intel Corporation 8 Series PCI Express Root Port 5 [8086:9c18] (rev e4)
        # Kernel driver in use: pcieport
        # Kernel modules: shpchp
        scripts/config -e PCIEPORTBUS -m HOTPLUG_PCI_SHPC
        # USB controller [0c03]: Intel Corporation 8 Series USB EHCI #1 [8086:9c26] (rev 04)
        # Subsystem: Hewlett-Packard Company 8 Series USB EHCI [103c:2b38]
        # Kernel driver in use: ehci-pci
        scripts/config -e USB_EHCI_PCI
        # ISA bridge [0601]: Intel Corporation 8 Series LPC Controller [8086:9c45] (rev 04)
        # Subsystem: Hewlett-Packard Company 8 Series LPC Controller [103c:2b38]
        # Kernel driver in use: lpc_ich
        # Kernel modules: lpc_ich
        scripts/config -m LPC_ICH
        # SATA controller [0106]: Intel Corporation 8 Series SATA Controller 1 [AHCI mode] [8086:9c03] (rev 04)
        # Subsystem: Hewlett-Packard Company 8 Series SATA Controller 1 [AHCI mode] [103c:2b38]
        # Kernel driver in use: ahci
        scripts/config -e SATA_AHCI
        # SMBus [0c05]: Intel Corporation 8 Series SMBus Controller [8086:9c22] (rev 04)
        # Subsystem: Hewlett-Packard Company 8 Series SMBus Controller [103c:2b38]
        # Kernel modules: i2c_i801
        scripts/config -m I2C_I801
        # Ethernet controller [0200]: Realtek Semiconductor Co., Ltd. RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller [10ec:8168] (rev 0c)
        # Subsystem: Hewlett-Packard Company RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller [103c:2b38]
        # Kernel driver in use: r8169
        # Kernel modules: r8169
        scripts/config -m R8169
        # Unassigned class [ff00]: Realtek Semiconductor Co., Ltd. RTS5229 PCI Express Card Reader [10ec:5229] (rev 01)
        # Subsystem: Hewlett-Packard Company RTS5229 PCI Express Card Reader [103c:2b38]
        # Kernel driver in use: rtsx_pci
        # Kernel modules: rtsx_pci
        scripts/config -m MFD_RTSX_PCI
        # Network controller [0280]: Broadcom Corporation BCM43142 802.11b/g/n [14e4:4365] (rev 01)
        # Subsystem: Hewlett-Packard Company BCM43142 802.11b/g/n [103c:804a]
        # Kernel driver in use: bcma-pci-bridge
        # Kernel modules: bcma
        # lsusb -v
        #   idVendor           0x0a5c Broadcom Corp.
        #   idProduct          0x216d
        #   bcdDevice            1.12
        #   iManufacturer           1 Broadcom Corp
        #   iProduct                2 BCM43142A0
        #   iSerial                 3 2C337AEE0604
        scripts/config -m B43 -m BCMA -m BT -m BT_BCM -m BT_HCIBTUSB -m BT_RFCOMM -m BT_HIDP
    fi

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

root-passwd() {
  chpasswd <<EOF
root:$ROOT_PASSWD
EOF
}

install-snapshot() {
  rm -rf /mnt/gentoo/var/tmp/portage
  btrfs su snapshot -r /mnt/root/root /mnt/root/.snapshots/root@$(sdate).install
}

sdate() {
    date -u +"%Y%m%dT%H%M%SZ";
}


if [ -z "$SCRIPT_STARTED" ]; then
    export SCRIPT_STARTED=1
    CMD="$(printf "bash %q" "$0")"
    for ARG in "$@"; do
        CMD="$CMD $(printf "%q" "$ARG")"
    done
    exec script -f -c "$CMD" "$(tempfile -p scrpt)"
fi

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
