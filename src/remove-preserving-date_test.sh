#!/bin/bash

testEquality() {
  local D=$(mktemp -d)
  mkdir -p "$D/dst" "$D/src/1/2/3"
  touch "$D/src/1/2/3/a" "$D/src/1/2/3/b"
  find "$D" -print0 | xargs -0 touch -d"@0"
  (cd "$D/src"; D="$D/dst" remove-preserving-date.sh 1/2/3/a)
  CH=$(rsync -nia --delete "$D/dst/" "$D/src/")
  assertEquals "$CH" "*deleting   1/2/3/b"$'\n'">f+++++++++ 1/2/3/a"
  rm -rf "$D"
}

. shunit2
