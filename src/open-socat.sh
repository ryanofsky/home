#!/bin/sh

for ARG in "$@"; do
  FILE="${ARG%%:*}"
  FILE="$(echo-relpath.sh "$FILE")"
  LINE="${ARG}:"
  LINE="${LINE#*:}"
  LINE="${LINE%%:*}"
  echo "$(readlink -f -- "$FILE")" | socat - TCP:localhost:17873
done
