#!/bin/sh

findroot () {
  local UP
  UP=
  while true; do
    if test -e "$UP$1"; then
      echo -n "$UP$1"
      return 0
    elif test "$(cd "$UP."; pwd)" = /; then
      echo -n "$1"
      return 1
    fi
    UP="../$UP"
  done
}

FILE="$1"
while true; do
  if FILE="$(findroot "$FILE")"; then
    echo -n "$FILE"
    exit 0
  fi
  NFILE="${FILE#*/}"
  if test "$NFILE" = "$FILE"; then
    NFILE=$(git ls-files | grep "\(^\|/\)$FILE" | tail -n1)
    if test -e "$NFILE"; then
      echo -n "$NFILE"
      exit 0
    fi
    echo -n "$1"
    exit 1
  fi
  FILE="$NFILE"
done
