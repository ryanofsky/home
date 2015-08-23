#!/bin/sh

ls -1 "$1" | while read F; do
  if [ -e "$2/$F" ]; then
    while read P1; do
      rm -v "$P1"
    done < "$1/$F"
  fi
done
