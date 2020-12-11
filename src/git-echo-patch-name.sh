#!/usr/bin/env bash

set -e

if [ $# != 1 ]; then
  echo "Error: expected 1 arg" 1>&2
  exit 1
fi

HASH="$1"
read PATCHID HASH2 < <(git show $HASH | git patch-id)
if [ "$HASH2" != "$HASH" ]; then
  echo "Error: wrong hash '$HASH2' '$HASH'" 1>&2
  exit 1
fi
echo $PATCHID
exit 0