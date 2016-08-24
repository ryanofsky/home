#!/bin/bash

# create parent directory containing a file
mkpar() {
    local d="${1%/*}"
    test -z "$d" || test "$d" = "$1" || mkdir -vp "$d"
}

ARCHIVE_SRC="/var/log"
ARCHIVE_DST="/var/archive/$(hostname)"

# generate unique destination filename using optional timestamp from reference file
archive-name() {
  local base="$1"
  local ref="$2"
  local dest="$ARCHIVE_DST/$base"
  if [ -n "$ref" ]; then
    local dest="$dest.$(date -u +"%Y-%m-%d-%H%M%S" -d@$(stat --printf '%Y' "$ref"))"
  fi
  if [ -e "$dest" ]; then
    local i=0; while [ -e "$dest.$i" ]; do let i++; done
    dest="$dest.$i"
  fi
  echo "$dest"
}

# relocate $ref file to destination named after $base
archive-log() {
  local base="$1"
  local ref="$2"
  test -e "$ref" || return
  local d="$(archive-name "$base" "$ref")"
  mkpar "$d"
  mv -iv "$ref" "$d"
}

# export journald file to destination named after $base
archive-journal() {
  local host="$1"
  local journal="$2"
  (
    cd "$ARCHIVE_SRC/journal/$host"
    test -e "$journal" || return 0
    mkdir tmp || return 1
    mv -i "$journal" tmp/
    local d="$(archive-name "journal/$host/$journal")"
    echo "$d"
    mkpar "$d"
    journalctl -D tmp -o export > "$d" || return 1
    touch -r "tmp/$journal" "$d" || return 1
    mkdir -p "archive"
    mv -i "tmp/$journal" "archive/${d##*/}" || return 1
    rmdir tmp || return 1
  )
}

archive-ls() {
    find "$ARCHIVE_SRC" -path "$ARCHIVE_SRC/journal/*/archive" -prune \
                        -o -path "$ARCHIVE_SRC/wtmp" -prune \
                        -o -path "$ARCHIVE_SRC/btmp" -prune \
                        -o -path "$ARCHIVE_SRC/lastlog" -prune \
                        -o -path "$ARCHIVE_SRC/tallylog" -prune \
                        -o -name '.keep_*' -prune \
                        -o -type f -print
}
