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

# print latest date in format used for snapshots
mirror-latest() {
    local dir="$1"
    date -u +"%Y%m%dT%H%M%SZ" --date=@$(find "$dir" -printf '%T@\n' | sort -n | tail -n1)
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

# git-pack (git_dir)
# repack loose objects & pack files without .keep tags into single new pack with .keep tag
# also pack refs and delete stale server-info
# warn about unexpected files in object and ref directories
mirror-git-pack() {
    local git_dir="$1"
    rm -vf "$git_dir/info/refs" "$git_dir/objects/info/packs"
    test ! -e "$git_dir/branches" || rmdir -v "$git_dir/branches"

    local pack=$(
        (
            for i in "$git_dir"/objects/pack/pack-????????????????????????????????????????.idx; do
                if [ -e "$i" ] && ! [ -e "${i%.idx}.keep" ]; then
                    git show-index < "$i" | cut -d' ' -f2
                fi
            done;
            local m=("$git_dir"/objects/??)
            if [ -e "${m[0]}" ]; then
                (cd "$git_dir/objects"; find ?? -type f -printf '%p\n' | sed 's:/::')
            fi
        ) | GIT_DIR="$git_dir" git pack-objects -q "$git_dir/objects/pack/pack" --honor-pack-keep --non-empty)

    if [ -n "$pack" ]; then
        run touch -r "$git_dir/objects/pack/pack-${pack}.idx" "$git_dir/objects/pack/pack-${pack}.keep"
        run chmod a-w "$git_dir/objects/pack/pack-${pack}.keep"
    fi

    GIT_DIR="$git_dir" git prune-packed
    for i in "$git_dir"/objects/pack/pack-????????????????????????????????????????.idx; do
        if [ -e "$i" ] && ! [ -e "${i%.idx}.keep" ]; then
            rm -fv "$i" "${i%.idx}.pack"
        fi
    done

    if [ -n "$(find "$git_dir/refs" -type f -'(' -name HEAD -prune -o -print -')')" ]; then
        GIT_DIR="$git_dir" run git pack-refs --all
    fi
    find "$git_dir/refs" -depth -mindepth 1 -type d -empty -delete
    if [ -n "$(find "$git_dir/objects" -type f -'(' -name 'pack-*' -prune -o -print -')')" ]; then
        echo "WARNING: Unexpected files found in $git_dir/objects"
    fi
    if [ -n "$(find "$git_dir/refs" -type f -'(' -name HEAD -prune -o -print -')')" ]; then
        echo "WARNING: Unexpected files found in $git_dir/refs"
    fi
    local find=(find "$git_dir" '-(' -path "$git_dir/objects/pack/pack-*.keep" -o -path "$git_dir/refs" ')' -prune -o -empty -print)
    if [ -n "$("${find[@]}")" ]; then
        echo "WARNING: Unexpected empty files/dirs found in in $git_dir:"
        "${find[@]}"
    fi
}

# safe-git-pick (git_dir) (backup_dir)
# modify $git_dir in-place similar to git-pack command above, but before doing
# this, create reflinked backup copy of it inside a backup directory (must
# already exist). delete the backup if no changes are made, but keep it and
# print a warning to manually check the changes if any are found
mirror-safe-git-pack() {
    local git_dir="$1"
    local backup_dir="$2"

    if ! [ -d "$backup_dir" ]; then
        echo "Error: safe-git-pack backup dir '$backup_dir' does not exist" >&2
        return 1
    fi

    local git_backup="$backup_dir/${git_dir//\//_}"
    while [ -e "$git_backup" ]; do git_backup="${git_backup}_"; done

    cp -a --reflink=auto "$git_dir" "$git_backup"
    mirror-git-pack "$git_dir"

    if [ -z "$(rsync -ncia --delete "$git_dir/" "$git_backup/")" ]; then
        rm -rf "$git_backup"
    else
        local check="git-contains.py ${git_backup} ${git_dir}"
        echo "Warning: Repacked git dir '$git_dir', verify with: $check"
        echo "$check" >> "$backup_dir/check.sh"
        echo "rsync -ncirltDHX --delete ${git_backup}/ ${git_dir}" >> "$backup_dir/check.sh"
    fi
}

# half unit-test for git-pack function. creates a temporary dummy git repository
# and calls git-pack on it, but doesn't do any automated error checking, just prints
# output for manual inspection
mirror-test-git-pack() {
    local d=$(mktemp -d)
    local git_dir="$d/.git"

    echo "=== mirror-git-pack init ==="
    git init "$d"
    local loose=$(echo loose | GIT_DIR="$git_dir" git hash-object -w --stdin)
    local keep=$(echo keep | GIT_DIR="$git_dir" git hash-object -w --stdin)
    local nokeep=$(echo nokeep | GIT_DIR="$git_dir" git hash-object -w --stdin)
    local p_keep=$( echo "$keep" | GIT_DIR="$git_dir" git pack-objects -q "$git_dir/objects/pack/pack")
    local p_nokeep=$( (echo "$keep"; echo "$nokeep") | GIT_DIR="$git_dir" git pack-objects -q "$git_dir/objects/pack/pack")
    touch "$git_dir/objects/pack/pack-${p_keep}.keep"
    GIT_DIR="$git_dir" git prune-packed
    echo

    echo "=== mirror-git-pack before keep=${keep:0:7} nokeep=${nokeep:0:7} loose=${loose:0:7} ==="
    find "$git_dir/objects" -type f | sort
    for f in "$git_dir"/objects/pack/pack-????????????????????????????????????????.idx; do
        echo "== $f =="
        git show-index < "$f"
    done
    echo

    echo "=== mirror-git-pack [1/2] ==="
    mirror-git-pack "$git_dir"
    echo

    echo "=== mirror-git-pack [2/2] ==="
    mirror-git-pack "$git_dir"
    echo

    echo "=== mirror-git-pack after ==="
    find "$git_dir/objects" -type f | sort
    for f in "$git_dir"/objects/pack/pack-????????????????????????????????????????.idx; do
        echo "== $f =="
        git show-index < "$f"
    done
}

# git-rsync ...
# wrapper around rsync to copy git dir to a destination, but exclude
# (and delete any exluded files on destination) working dir git files
# like the index and caches
mirror-git-rsync() {
    run rsync \
        -aDHX \
        --inplace \
        --numeric-ids \
        --chown=1000:1000 \
        --chmod=u=rwX,go=rX \
        --exclude=/index \
        --exclude=/ORIG_HEAD \
        --exclude=/FETCH_HEAD \
        --exclude=/COMMIT_EDITMSG \
        --exclude=/gitk.cache \
        --exclude=/MERGE_RR \
        --exclude=/worktrees \
        --exclude=/qgit_cache.dat \
        --delete --delete-excluded "$@"
}

# snap-start (prev) (tmp)
mirror-snap-start() {
    local prev="$1"
    local tmp="$2"
    if [ -z "$prev" ] || ! [ -d "$prev" ]; then
        echo "Error: can't create snapshot '$tmp' from invalid base '$prev'.">&2
        return 1
    fi
    if [ -e "$tmp" ]; then
        echo "Error: can't create snapshot '$tmp' from '$prev' because it already exists.">&2
        return 1
    fi
    run btrfs su snapshot "$prev" "$tmp"
}

# snap-finish (prev) (tmp) (new)
mirror-snap-finish() {
    local prev="$1"
    local tmp="$2"
    local new="$3"
    if ! [ -d "$tmp" ]; then
        run btrfs property set -ts "$new" ro true
    elif [ -z "$(rsync -nciaDHX --delete "$tmp/" "$prev")" ]; then
        run btrfs su delete "$tmp"
    elif [[ $prev < $new ]]; then
        run mv -vT "$tmp" "$new"
        run btrfs property set -ts "$new" ro true
    else
        echo "Error: can't rename '$tmp' to '$new' because doesn't follow previous snapshot '$prev'">&2
        return 1
    fi
}

# remotely list snapshots matching pattern
mirror-ssh-ls() {
    local remote_host="$1"
    local remote_dir="$2"
    local subvol="$3"
    ssh -n "$remote_host" "cd ${remote_dir@Q}; ls -1d ${subvol@Q}@* 2>/dev/null || true"
}

mirror-log() {
    local snap_dir="$1"
    local prev=
    local prev_name=
    for snap in $(cd "$snap_dir"; ls -1); do
        name="${snap%@*}"
        date="${snap#*@}"
        date="$(sed 's,\(....\)\(..\)\(..\)T\(..\)\(..\)\(..\).*,\1-\2\-\3T\4:\5:\6Z,' <<<"$date")"
        if [ "$name" != "$prev_name" ]; then
            echo "$date -- created $name@"
        else
            echo "$date -- updated $name@ (rsync -nai --delete $snap/ $prev)"
        fi
        prev="$snap"
        prev_name="$name"
    done | sort -r
}

run() {
    echo "$@"
    "$@"
}

if [ "$#" -ne 0 ]; then
    CMD="$1"
    shift
    "mirror-$CMD" "$@"
fi
