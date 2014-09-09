#!/bin/bash

if [ $# != 1 ]; then
  echo "Error: expected 1 arg" 1>&2
  exit 1
fi

HASH="$1"
TIME=$(git log -n1 --format=%at "$HASH")
PATCHID=$(git-echo-patch-name.sh $HASH)

num() {
  local NAME="$1"
  git for-each-ref --format='%(refname:short)' \
      "refs/$NAME.*" | {
    NMAX=0
    FOUND=
    while read REF; do
      FOUND=1
      local N="${REF#*.}"
      if [ "$N" -gt "$NMAX" ]; then
        NMAX="$N"
      fi
    done
    if [ -n "$FOUND" ]; then
      echo "$NAME.$(($NMAX + 1))"
    else
      echo $NAME
    fi
  }
}

TIMES=/tmp/time-"${GIT_DIR////-}"
if [ ! -e "$TIMES" ]; then
  (
    git show-ref | grep -v " refs/tags/archive/" | grep -v " refs/exported/" | grep -v " refs/remotes/" | grep -v "stash" |
    while read RHASH REF; do
      RANGE=$RHASH
      BASE=$(git-echo-base.sh $RHASH)
      if [ -n "$BASE" ]; then
        RANGE=$BASE..$RANGE
      fi
      git log --format="%H %at" $RANGE |
      while read CHASH CTIME; do
        CPATCHID="$(git-echo-patch-name.sh $CHASH || echo empty)"
        echo "$CHASH $REF $CTIME $CPATCHID"
      done
    done
  ) > $TIMES
fi

EXACT=()
INEXACT=()
while read CHASH REF CTIME CPATCHID; do
  if [ "$CTIME" = "$TIME" ]; then
    if [ "$CPATCHID" = "$PATCHID" ]; then
      EXACT=("${EXACT[@]}" "$CHASH $REF")
    else
      INEXACT=("${INEXACT[@]}" "$CHASH $REF")
    fi
  fi
done < "$TIMES"

if [ "${#EXACT[@]}" -gt 0 ]; then
  MATCHES=("${EXACT[@]}")
  PREF=1  
else
  MATCHES=("${INEXACT[@]}")
  PREF=0
fi

for MATCH in "${MATCHES[@]}"; do
  read CHASH REF <<<"$MATCH"
  REL=$(git name-rev --name-only --always --refs=$REF $CHASH)
  REF="${REF#refs/}"
  NUMREF=$(num $REF)
  REL="${REL/#${REF}/${NUMREF}}"
  REL="${REL#tags/}"
  echo "$PREF $REL $CHASH"
done
