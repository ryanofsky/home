#!/bin/bash

set -e

cpinfo() {
  local info_dir="$1"
  local dest_dir="$2"
  find "$dest_dir" -printf '%P\n' | while read path; do
    local info_file="$info_dir/${path##*/}"
    local dest_file="$dest_dir/$path"
    if [ ! -e "$info_file.info" ]; then continue; fi
    if [ -e "$dest_file.info" ]; then continue; fi

    local ftime="$(stat --printf=%Y "$info_file.info")"
    local stime="$(stat --printf=%Y "$dest_file")"
    local u_file="${info_file}_"
    while [ -e "$u_file.info" ]; do
      local utime="$(stat --printf=%Y "$u_file.info")"
      if ((utime >= stime && utime <= ftime)); then
          info_file="$u_file"
          ftime="$utime"
      fi
      u_file="${u_file}_"
    done

    cp -av "$info_file.info" "$dest_file.info"
    local mtime_long="$(stat --printf=%y "$info_file")"
    local ftime_long="$(stat --printf=%y "$info_file.info")"
    local stime_long="$(stat --printf=%y "$dest_file")"
    if [ "$mtime_long" != "$ftime_long" ]; then
      printf "        $mtime_long (modified time %s)\n" "$info_file"
      printf "        $ftime_long (finish time   %s)\n" "$info_file.info"
      printf "  %+-5i $stime_long (save time     %s)\n" "$((stime - ftime))" "$dest_file"
      touch -r "$info_file" "$dest_file"
    fi
  done
}

INFO_DIR="$1"
shift
for DEST_DIR in "$@"; do
  cpinfo "$INFO_DIR" "$DEST_DIR"
done
