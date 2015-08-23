#!/bin/sh

mkdir -p "$2"
find "$1" -type f | while read F; do
  S=$(tr -d '\r' < "$F" | grep -v '^X-Keywords:' | md5sum | cut -d' ' -f1)
  echo "$F" >> "$2/$S"
done
