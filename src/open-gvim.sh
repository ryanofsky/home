#!/bin/sh

for ARG in "$@";
do
  FILE="${ARG%%:*}";
  FILE="$(echo-relpath.sh "$FILE")"
  LINE="${ARG}:";
  LINE="${LINE#*:}";
  LINE="${LINE%%:*}";
  if [ -n "$LINE" ]; then
      echo gvim --remote-tab +"$LINE" "$FILE";
      gvim --remote-tab +"$LINE" "$FILE";
  else
      echo gvim --remote-tab "$FILE";
      gvim --remote-tab "$FILE";
  fi;
done
