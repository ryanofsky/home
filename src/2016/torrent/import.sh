#!/bin/bash

set -x
set -e

cd $(dirname $0)

TMP_DIR=/mnt/fort/_tmp/torrent
STATES_DIR=$TMP_DIR/states
SORT_FILE=$TMP_DIR/states-sort
JSON_DIR=$TMP_DIR/json

# List input directories. Download dir is one directory that is
# input/output.
DOWNLOAD_DIR=/mnt/fort/_download
DOWNLOAD_DIR=$TMP_DIR/_download # For testing only
STATES=(
old.3/latest/old/2009-07-26-backup/root/home/russ/.azureus/torrents
old.47/latest/old/2012-01-28-rescue-toaster-root/home/russ/.azureus/torrents
old.5/latest/old/2011-10-30-russ/.azureus/torrents
old.9/latest/old/2012-02-15-russ/.azureus/torrents
old.34/latest/old/2011-07-17-rabbit-root/home/russ/.config/deluge/state
old.12/latest/old/2012-02-15-rabbit-russ/.config/deluge/state
old.5/latest/old/2011-10-30-russ/.config/deluge/state
old.9/latest/old/2012-02-15-russ/.config/deluge/state
old.47/latest/old/2012-01-28-rescue-toaster-root/home/russ/.config/deluge/state
old.58/latest/old/2014-05-21-homes/russ/.config/deluge/state
old.58/latest/old/2014-05-21-homes/pia/.config/deluge/state
$DOWNLOAD_DIR/pia-config-deluge/*/state
$DOWNLOAD_DIR/pia2-config-deluge/*/state
)
DATA_DIRS=(
$DOWNLOAD_DIR
/mnt/fort/.snapshots/share@20140527T001746Z
/mnt/fort/_tmp/data/old.56/latest/old/2014-03-25-share
/mnt/fort/_tmp/data/old.57/latest/old/2014-03-25-share
)

# Set up temporary directory with an embedded mutable copy of
# _download directory for testing.
test ! -e $TMP_DIR/_download || btrfs su delete $TMP_DIR/_download
test ! -e $TMP_DIR || btrfs su delete $TMP_DIR
btrfs su create $TMP_DIR
btrfs su snapshot /mnt/fort/_download $TMP_DIR/_download

# Figure out ordering for state dirs.
rm -rf $STATES_DIR $SORT_FILE
for STATE in "${STATES[@]}"; do
  if [ -z "${STATE%old.*}" ]; then
     BUP_DIR=/mnt/fort/data bup restore $STATE/. -C $STATES_DIR/$STATE
     STATE_DIR=$STATES_DIR/$STATE
  else
     STATE_DIR=$STATE
  fi
  MTIME=$(find $STATE_DIR -type f -printf '%T@ %p\n' | sort | tail -n1 | cut -f1 -d' ')
  echo "$MTIME $STATE_DIR $STATE" >> $SORT_FILE
done

# Process state dirs.
rm -rf $JSON_DIR
mkdir $JSON_DIR
(cd $JSON_DIR; git init)
while read MTIME STATE_DIR STATE; do
  python -c "import torrent; torrent.tojson('$STATE_DIR', '$JSON_DIR')"
  (cd $JSON_DIR; git add .; git commit --allow-empty -m "Import torrents from $STATE")
done < <(sort -n $SORT_FILE)
echo "Check overridden states with (cd $JSON_DIR; git log -p -U0 --diff-filter=M)"

# Create symlink directories.
rm -rf $DOWNLOAD_DIR/symlinks
for DATA_DIR in "${DATA_DIRS[@]}"; do
  if [ "$DATA_DIR" != "$DOWNLOAD_DIR" ]; then
     python -c "import torrent; torrent.make_symlink_tree('$DATA_DIR', '$DOWNLOAD_DIR/symlinks$DATA_DIR')"
  fi
done

# Create torrent dir with symlinks to data files.
rm -rf $DOWNLOAD_DIR/torrent
mkdir $DOWNLOAD_DIR/torrent
python -c "import torrent; torrent.find_files('$JSON_DIR', '$DOWNLOAD_DIR', '$DOWNLOAD_DIR/torrent')"
echo "Search symlinks with (cd $DOWNLOAD_DIR/torrent; find -type l -printf '%P ---- %l\n')"

# Add checksums.
#python -c "import torrent; torrent.load_sums('$JSON_DIR', '$DOWNLOAD_DIR/torrent', '/mnt/fort/_tmp/torrent.sums')"
python -c "import torrent; torrent.compute_sums('$JSON_DIR', '$DOWNLOAD_DIR/torrent')"
(cd $JSON_DIR; git add .; git commit -m "Run compute_sums to get md5 checksums.")
#python -c "import torrent; torrent.dump_sums('$JSON_DIR', '$DOWNLOAD_DIR/torrent', '/mnt/fort/_tmp/torrent.sums')"

# Move data and point symlinks into torrent directory.
python -c "import torrent; torrent.move_torrents('$DOWNLOAD_DIR', '$DOWNLOAD_DIR/torrent')"
echo "Check content (cd $DOWNLOAD_DIR; find -printf '%P ---- %T@ ---- %l\n' | sort)"
