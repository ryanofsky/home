#!/usr/bin/env bash

frameid() {
  xwininfo -root -tree | sed -n 's/^        \(   \)\?\(0x[0-9a-f]\+\) .*: ("emacs" "Emacs").*/\2/p' | head -n1
}

O=()
while test -n "$1"; do
  case "$1" in
   -c)
      O=("${O[@]}" "$1")
      shift
      ;;
   --)
      shift
      break;
      ;;
   -*)
      echo "Error: unknown option $1" >&2
      exit 1
      ;;
   *)
      break;
  esac
done

O=("${O[@]}" "-n")

if [ -n "$DISPLAY" ]; then
  f=$(frameid)
  if [ -z "$f" ]; then
     run.sh emacsclient -c -n
     f=$(frameid)
  fi
  test -z "$f" || run.sh xdotool windowactivate "$f"
fi

for ARG in "$@"; do
  FILE="${ARG%%:*}"
  FILE="$(echo-relpath.sh "$FILE")"
  LINE="${ARG}:"
  LINE="${LINE#*:}"
  LINE="${LINE%%:*}"
  if [ -n "$LINE" ]; then
      run.sh emacsclient "${O[@]}" +"$LINE" "$FILE"
  else
      run.sh emacsclient "${O[@]}" "$FILE"
  fi
done
