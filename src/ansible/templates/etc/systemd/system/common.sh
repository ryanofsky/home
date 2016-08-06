#!/bin/bash

# create parent directory containing a file
mkpar() {
    local d="${1%/*}"
    test -z "$d" || test "$d" = "$1" || mkdir -vp "$d"
}

# generate unique destination filename using optional timestamp from reference file
archive-name() {
  local base="$1"
  local ref="$2"
  local dest="/var/archive/$(hostname)/$base"
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
    cd "/var/log/journal/$host"
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
    find /var/log -path '/var/log/journal/*/archive' -prune \
                  -o -path '/var/log/wtmp' -prune \
                  -o -path '/var/log/btmp' -prune \
                  -o -path '/var/log/lastlog' -prune \
                  -o -path '/var/log/tallylog' -prune \
                  -o -name '.keep_*' -prune \
                  -o -type f -print
}
