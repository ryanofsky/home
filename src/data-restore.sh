#!/bin/bash

set -e
set -x

btrfs property set -ts /mnt/fort/_tmp/data ro false
for p in "$@"; do
  BUP_DIR=/mnt/fort/data bup restore $p/. -C /mnt/fort/_tmp/data/$p
  bind="mount --bind /mnt/fort/_tmp/data/$p /mnt/data/$p"
  echo "$bind" >> /mnt/fort/_tmp/data/bind.sh
  test ! -e "/mnt/data/$p" || $bind
done
btrfs property set -ts /mnt/fort/_tmp/data ro true
