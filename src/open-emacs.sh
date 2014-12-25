#!/bin/sh

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
