#!/bin/sh

ls -1 "$1" | while read F; do
  if [ ! -e "$2/$F" ]; then
    echo "$F"
    sed 's/^/  /' < "$1/$F"
  fi
done
