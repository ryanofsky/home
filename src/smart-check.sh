#!/usr/bin/env bash

# Usage:
#   smart status
#   smart long
# https://help.ubuntu.com/community/Smartmontools

DISKS="${DISKS:-sda book sea hit mup bup fort}"

run() {
  local CMD=$(echo "$@")
  echo
  echo ================================================================================
  printf "===  %-71s ===\n" "$CMD"
  echo ================================================================================
  echo
  "$@"
}

cmd() {
  local DISK="$1" O=
  if [ "$DISK" = book -o "$DISK" = fort ]; then
    O="-d sat"
  fi
  shift
  run sudo smartctl "$@" $O "/dev/$DISK"
}

for CMD in "$@"; do
  if [ "$CMD" = abort ]; then
    for DISK in $DISKS; do
      cmd $DISK -X # self test
      cmd $DISK -o off # offline tests
      cmd $DISK -s off # smart online data collection
      cmd $DISK -s on  # smart online data collection
      cmd $DISK -S on  # autosave
    done
    continue
  fi

  CHECK=1
  case "$CMD" in
    status)      LOGTYPE=error; CHECK=;;
    offline)     LOGTYPE=error;;
    log)         LOGTYPE=selftest; CHECK=;;
    short|long)  LOGTYPE=selftest;;
    *) echo $CMD is an unrecognised test type. Skipping... && continue
  esac

  if [ -n "$CHECK" ]; then
    MAX=0
    for DISK in $DISKS; do
      MIN=$(cmd $DISK -t $CMD | grep 'Please wait' | awk '{print $3}')
      if [ "$CMD" = "offline" ]; then
        echo Check $DISK - $CMD test in $MIN seconds
      else
        echo Check $DISK - $CMD test in $MIN minutes
      fi
      [ "$MIN" -gt $MAX ] && MAX="$MIN"
    done
    if [ $CMD = "offline" ]; then
      echo "Waiting $(($MAX / 60)) minutes for all tests to complete"
    else
      echo "Waiting $MAX minutes for all tests to complete"
      MAX="${MAX}m"
    fi
    sleep "$MAX"
  fi

  for DISK in $DISKS; do
    cmd $DISK -H -l $LOGTYPE
  done
done
