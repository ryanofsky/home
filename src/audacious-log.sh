#!/bin/sh

# Audacious song change plugin setting:
#
# /home/russ/src/audacious-log.sh {song-start,song-end,playlist-end,title-change} artist="%a" title="%T" album="%b" currently-playing="%p" length="%l" channels="%c" frequency="%F" rate="%r" playlist-position="%t" file="%f"
#
# Log string can be split with python shlex.split.

s="$(date -Ins)"
for arg in "$@"; do
  s="$s $(printf "%q" "$arg")"
done
echo "$s" >> /home/russ/russ/2016/audacious.log
