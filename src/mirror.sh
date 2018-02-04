#!/bin/bash

set -e

# replace btrfs directory with btrfs subvolume
mirror-tovol() {
    local path="${1%/}"
    mv -v "$path" "${path}_tovol_"
    btrfs su create "$path"
    cp -a --reflink=always "${path}_tovol_/." "$path"
    rm -rf "${path}_tovol_"
}

# send (local_dir) (remote_dir) (snapshot...)
# print btrfs send/receive commands for sending local subvolume to remote
mirror-send() {
    local local_dir="$1"
    shift
    local remote_dir="${1##*:}"
    local remote_host=
    local remote_receive="btrfs receive $remote_dir"
    if [ "$remote_dir" != "$1" ]; then
        remote_host="${1%:*}";
        remote_receive="ssh $remote_host $remote_receive"
    fi
    shift
    for subvol in "$@"; do
        readarray -t local_ls < <(cd "$local_dir"; ls -1d "$subvol@"* 2>/dev/null || true)
        readarray -t remote_ls < <(
            if [ -n "$remote_host" ]; then
                mirror-ssh-ls "$remote_host" "$remote_dir" "$subvol"
            else
               cd "$remote_dir"; ls -1d "$subvol@"* 2>/dev/null || true
            fi
        )

        # If sending local snapshot 3, and remote snapshots are 1, 2, 4, and 5,
        # use snapshot 4 as the diff base. In general always use earliest
        # following snapshot if one exists as the base, otherwise fall back to
        # latest preceding snapshot. Assuming snapshots tend to grow over time,
        # preferring following snapshots over preceding ones should send less
        # data.
        local i=0
        local j=0
        local remote_subvol=
        while ((i < ${#local_ls[@]})); do
            local local_subvol="${local_ls[$i]}"
            if ((j < ${#remote_ls[@]})); then
                remote_subvol="${remote_ls[$j]}"
                if [ "$remote_subvol" \< "$local_subvol" ]; then ((j++)); continue; fi
            fi

            if [ "$remote_subvol" = "$local_subvol" ]; then
                echo "# Skipping $local_subvol, already exists"
            elif [ -n "$remote_subvol" ]; then
                echo "btrfs send -p $local_dir/$remote_subvol $local_dir/$local_subvol | $remote_receive"
            else
                echo "btrfs send $local_dir/$local_subvol | $remote_receive"
            fi

            if [ "$remote_subvol" \< "$local_subvol" ]; then remote_subvol="$local_subvol"; fi
            ((i++))
        done
    done
}

# changed (snapshot1_path) (subvol2_path) && echo same || echo different
# compare generation numbers on two subvolume/snapshots
mirror-changed() {
    test "$(btrfs subvolume find-new "$1" 99999999)" != "$(btrfs subvolume find-new "$2" 99999999)"
}

# ls (directory) [strip prefix]
#
# print child subvolumes of whatever subvolume contains directory,
# and optionally filter/strip prefix, since output weirdly contains
# volume name as first path component
#
# not recursive, and awkwardly includes subvolumes not directly in
# provided path, elsewhere on same subvolume
mirror-ls() {
    local path="$1"
    local strip="$2"
    btrfs su list -o "$path" | sed -n "s:^ID [0-9]\\+ gen [0-9]\\+ top level [0-9]\\+ path $strip::p"
}

# print current date in format used for snapshots
mirror-date() {
    date -u +"%Y%m%dT%H%M%SZ"
}

# snap (src) (dst) (sdate)
# print command to create $dst@$sdate snapshot from $src ONLY if $src has been
# modified since the previous snapshot
mirror-snap() {
    local src="$1"
    local dst="$2"
    local sdate="$3"
    local prev=$(ls -1d "$dst@"* 2>/dev/null | tail -n1 || true)
    if test -z "$prev" || mirror-changed "$prev" "$src"; then
        echo btrfs su snapshot -r "$src" "$dst@$sdate"
    else
        echo "# $prev is up to date"
    fi
}

# snaps (path) (strip) (prefix)
# search path for live subvolumes not in .mirror/.snapshot directories that have
# been modified since previous snapshot, and print commands to create new
# snapshots with current date
mirror-snaps() {
    local path="$1"
    local strip="$2"
    local prefix="$3"
    local sdate="$(mirror-date)"
    mirror-ls "$path" "$strip" | while read subvol; do
        if [[ $subvol == .snapshots/* ]]; then continue; fi
        if [[ $subvol == .mirror/* ]]; then continue; fi
        local dest=$(sed s:/:-:g <<<"$subvol" | sed "s/^_tmp-//")
        test -z "$prefix" || dest="$prefix-$dest"
        mirror-snap "$path/$subvol" "$path/.snapshots/$dest" "$sdate"
    done
    test -z "$prefix" || mirror-snap "$path" "$path/.snapshots/$prefix" "$sdate"
    return 0
}

# output list of snapshots in a directory that can be passed as arguments to mirror-send
# compare each snapshot in directory against global EXPECT array
# if size is too big or snapshot name is unknown, print error
mirror-check() {
    local dir="$1"
    local subvol
    local -A good
    local -A bad
    while read subvol; do
        local base="${subvol%@*}"
        local expect="${EXPECT[${base}]}"
        if [ -z "$expect" ]; then
            echo "Error: Unknown snapshot $subvol" >&2
        elif [ "$expect" != skip ]; then
            local size=$(du -ms "$dir/$subvol" | cut -f1)
            if [ "$size" -le "$expect" ]; then
                good["$base"]=1
            else
                echo "Error: snapshot $subvol too big ($size > $expect mb)" >&2
                bad["$base"]=1
            fi
        fi
    done < <(ls -1 "$dir")

    local k
    for k in "${!good[@]}"; do
      test -n "${bad[$k]}" || echo "$k"
    done | sort
}

# remotely list snapshots matching pattern
mirror-ssh-ls() {
    local remote_host="$1"
    local remote_dir="$2"
    local subvol="$3"
    ssh -n "$remote_host" "cd ${remote_dir@Q}; ls -1d ${subvol@Q}@* 2>/dev/null || true"
}

if [ "$#" -ne 0 ]; then
    CMD="$1"
    shift
    "mirror-$CMD" "$@"
fi
