#!/bin/bash

R=mini
D=/mnt/fort/_download
S=/home/pia/.config/deluge/state
RO=/home/pia/torrent
RW=/home/pia/torrent.rw
NEW=/mnt/hd/pia

# Escape $D for python regex
DRE="$(python -c "import re, sys; sys.stdout.write(re.escape(sys.stdin.read()))" <<<"$D")"

download() {
    mkdir deluge.download torrent torrent.rw
    remote export-torrents
    rsync -av --remove-source-files "$R:$D/new/deluge.download/" deluge.download/
    sudo mv -ivT deluge.download "$S"
    sudo chown -R pia:pia "$S"
    sshfs -o allow_root,ro "$R:$D/torrent" torrent
    sshfs -o allow_root "$R:$D/new/torrent.rw" torrent.rw

    sudo mkdir "$RO" "$RW"
    sudo bindfs -u pia -g pia -p 0644,a+X torrent "$RO"
    sudo bindfs -u pia -g pia -p 0644,a+X torrent.rw "$RW"

    sudo mkdir "$NEW"
    sudo chown pia:pia "$NEW"
}

save() {
    pgrep -a deluge && exit 1

    sudo umount "$RO" || true
    sudo umount "$RW" || true
    sudo rmdir "$RO" "$RW" || true
    fusermount -u torrent || true
    fusermount -u torrent.rw || true
    rmdir torrent torrent.rw || true

    sudo mv -ivT "$S" deluge.save
    sudo chown -R "$USER" deluge.save
    ssh "$R" mkdir -p "$D/new"
    rsync -av --remove-source-files --ignore-existing deluge.save/ "$R:$D/new/deluge.save/"
    rmdir deluge.save

    sudo chown -R "$USER" "$NEW"
    rsync -av --remove-source-files --ignore-existing "$NEW/" "$R:$D/new/share.save/"
    find "$NEW" -depth -type d -print0 | sudo xargs -r0 rmdir

    remote import-torrents

    cat <<EOF

    Manual steps:
        cd $D
        git add torrent.json
        find torrent -type f | sort | git annex add --batch | grep -v '^$'
        git commit -m 'add new/changed torrent files to git-annex'
EOF
}

remote() {
    rsync -av ../symlink/sym.py torrent.py run.sh "$R:"
    ssh $R ./run.sh "$@"
}

export-torrents() {
    mkdir "$D/new"
    mkdir "$D/new"/{deluge.download,torrent.rw}
    python2 -c "import torrent; torrent.select_torrents('$D/torrent.json', '$D/torrent', '$D/new/deluge.download', '$RO', '$RW')" | while read ID; do
        cp -aLiv --reflink=always "$D/torrent/$ID" "$D/new/torrent.rw/$ID"
        find "$D/new/torrent.rw/$ID" -type c -print0 | xargs -r0 rm -v
    done
}

import-torrents() {
    rmdir -v "$D/new/deluge.download" || true
    mkdir "$D/new/deluge.save.json" "$D/new/torrent.save"

    # Update torrent folder with new torrents.
    python2 -c "import torrent; torrent.import_torrents('$D/new/deluge.save', '$D/new/deluge.save.json'); torrent.find_files('$D/new/deluge.save.json', '$D/new/share.save', '$D/new/torrent.save', skip_empty=True)"
    ./sym.py find -0 -r "$D/new/torrent.save" "$DRE/new/share\\.save/.*" | xargs -0 ./sym.py reverse
    test -z "$(ls -A "$D/new/torrent.save")" || mv -iv "$D/new/torrent.save"/* "$D/torrent"
    rm -rv "$D/new/deluge.save.json"
    rmdir -v "$D/new/torrent.save"

    # Update share.save folder with symlinks to new torrents.
    ./sym.py find -0 -r -s "$D/torrent/\\1" "$D/new/share.save" "$DRE/new/torrent\\.save/(.*)"
    mkdir -p "$D/share.save"
    mv -iv "$D/new/share.save"/* "$D/share.save"
    rmdir -v "$D/new/share.save"

    # Update torrent folder with existing torrents.
    (
        cd "$D"
        local id old new
        mkdir -p "$D/new/torrent.rw"
        ls -1A "$D/new/torrent.rw" | while read id; do
            find "$D/new/torrent.rw/$id" -type f -printf '%P\n' | while read f; do
                old="torrent/$id/$f"
                new="new/torrent.rw/$id/$f"

                if test -e "$old"; then
                    if cmp "$old" "$new"; then
                        rm -v "$new"
                    else
                        git rm -f --cached "$old"
                        rm -v "$old"
                        mv -ivT "$new" "$old"
                    fi
                else
                    mkdir -p "$(dirname "$old")"
                    mv -ivT "$new" "$old"
                fi
            done
        done
        find "$D/new/torrent.rw/$id" -depth -type d -print0 | xargs -r0 rmdir -v
    )

    # Update torrent.json folder.
    python2 -c "import torrent; torrent.import_torrents('$D/new/deluge.save', '$D/torrent.json')"
    rm -rv "$D/new/deluge.save"
    rmdir -v "$D/new"
}

sums() {
    python2 -c "import torrent; torrent.compute_sums('$D/torrent.json', '$D/torrent')"
}

symlinks() {
    # FIXME: make sketch code below work
    exit 0
    find share -type -l -print0 | xargs -r0 readlink -f > 1
    find share.save -type -l -print0 | xargs -r0 readlink -f > 1
    find torrent -printf '%P\n' > 2
    comm -23 1 2
}

set -e
set -x
set -o pipefail

cd $(dirname $0)
"$@"
