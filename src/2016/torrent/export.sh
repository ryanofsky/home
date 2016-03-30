#!/bin/bash

set -x
set -e

cd $(dirname $0)

#OUT=$(mktemp -d)
OUT=/home/russ/.local/tmp/tmp.xFhvWhycVv
python -c "import torrent; torrent.select_torrents('/home/russ/src/torrent', '/mnt/download/torrent', '$OUT')"

set +x

MNT=/home/russ/.local/tmp/pia-mnt


echo "(cd ~src/torrent; git diff -U0)"
echo sudo rsync -av --delete $OUT/ /home/pia/.config/deluge/state/
echo sudo chown -R pia:pia /home/pia/.config/deluge/state/
echo mkdir -p $MNT
echo sudo bindfs -u pia -g pia -p 0644,a+X $MNT /home/pia/torrent

(
  cd $OUT;
  for f in *.torrent; do
      f="${f%.torrent}"
      echo mkdir -p $MNT/$f
      echo sshfs -o allow_root mini:/mnt/download/torrent/$f $MNT/$f
  done
)

echo "find $MNT -type l -printf 'rm %p # symlink to %l\n'"
echo "find $MNT -type l -print0 | xargs -0 rm -v"
