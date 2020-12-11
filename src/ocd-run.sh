#!/usr/bin/env bash

export NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export DIR="$HOME/run/$1/$(date -d "$NOW" +"%Y-%m-%dT%H%M%SZ")"
export TMPDIR="$DIR/tmp"
export DESC="$DIR/desc.txt"

if ! [ -x "./$1" ]; then
  echo "Error: './$1' not executable file." >&2
  exit 1
fi

mkdir -p "$DIR" "$TMPDIR"
INFO="$DIR/info.txt"
STATUS="$DIR/status.txt"
OUT="$DIR/out.txt"
TIMES="$DIR/times"
TIME="$DIR/time.txt"
EXEC="$DIR/exec.txt"

cp -av "$1" "$EXEC"
shift
CMD="$EXEC"
for arg in "$@"; do
  CMD="$CMD $(printf "%q" "$arg")"
done

echo "Date:    $(date -d "$NOW")" > "$INFO"
echo "Command: $CMD" >> "$INFO"
echo "Host:    $(hostname)" >> "$INFO"
echo "Pwd:     $(pwd)" >> "$INFO"
echo "=====" >> "$INFO"
cat "$INFO"
echo "=====" >> "$INFO"
env >> "$INFO"
env time --verbose --output="$TIME" script -f -q -e -c"$CMD" -t"$TIMES" "$OUT"
RET="$?"
echo "====="
echo "Start:   $(date -d "$NOW") ($NOW)" > "$STATUS"
echo "Done:    $(date)" >> "$STATUS"
echo "Status:  $RET" >> "$STATUS"
cat "$STATUS"
echo "Desc:    $DESC"
exit "$RET"
