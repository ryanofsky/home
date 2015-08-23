#!/bin/bash

for f in "$@"; do
  echo $f
  cp $f /tmp/t0
  grep -v '^using.*::[^:]*;$' "$f" > /tmp/t1
  for n in `sed -n 's/^using.*::\([^:]*\);$/\1/p' "$f"`; do
    if grep -q "$n" /tmp/t1; then
      echo found $n
    else
      echo not found $n
      sed -i /$n/d /tmp/t0
    fi
  done
  diff -u $f /tmp/t0
  cp -fv /tmp/t0 $f
done
