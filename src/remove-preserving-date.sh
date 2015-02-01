#!/bin/bash

# Move files from $PWD to $D preserving directory structure and directory
# timestamps.

run() {
  test -n "$V" && echo "$@"
  "$@"
}

armove() {
  local SRC="$1"
  local DST="$2"
  local FILE="$3"
  local DIR="${FILE%%/*}"
  if [ "$DIR" = "$FILE" ]; then
    local TMP="$(mktemp)"
    run touch --reference="$SRC" "$TMP"
    run cp -an --reflink "$SRC/$FILE" "$DST/$FILE"
    run rm -r "$SRC/$FILE"
    run touch --reference="$TMP" "$SRC"
    rm -f "$TMP"
    if [ -e "$SRC/FILE" -o -h "$SRC/FILE" ]; then
      echo "Failed to move '$SRC/FILE'" 1>&2
      exit 1
    fi
  else
    run mkdir -p "$DST/$DIR"
    run chown --reference="$SRC/$DIR" "$DST/$DIR"
    run chmod --reference="$SRC/$DIR" "$DST/$DIR"
    armove "$SRC/$DIR" "$DST/$DIR" "${FILE#*/}"
  fi
  run touch --reference="$SRC" "$DST"
}

if [ -z "$D" ]; then
  echo "Bad destination D='$D'" 1>&2
  exit 1
fi

while [[ $# > 0 ]]; do
  if [ "$1" != "${1#/}" ]; then
    echo "Skipping '$1'. Not relative path." 1>&2
  elif ! [ -e "$1" -o -h "$1" ]; then
    echo "Skipping '$1'. Path doesn't exist." 1>&2
  else
    armove . "$D" "$1"
  fi
  shift
done
