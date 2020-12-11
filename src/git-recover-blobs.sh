#!/usr/bin/env bash

set -x
set -e

mkdir -p /tmp/dump
git fsck --full --unreachable --no-reflog | while read UN BLOB HASH; do
  if [ "$UN $BLOB" = "unreachable blob" ]; then
    git cat-file -p "$HASH" > "/tmp/dump/$HASH"
  fi
done