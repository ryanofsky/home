#!/usr/bin/env bash

# Audacious song change plugin setting:
#
# /home/russ/src/audacious-log.sh {song-start,song-end,playlist-end,title-change} artist="%a" title="%T" album="%b" currently-playing="%p" length="%l" channels="%c" frequency="%F" rate="%r" playlist-position="%t" file="%f"
#
# Log string can be split with python shlex.split.

# urldecode from https://gist.github.com/cdown/1163649
urldecode() {
    local url_encoded="${1//+/ }"
    printf '%b' "${url_encoded//%/\\x}"
}

s="$(date -Ins)"
for arg in "$@"; do
    if [[ "$arg" == file=file://* ]]; then
        file="${arg#file=file://}"
        file="$(urldecode "$file")"
        file="$(readlink -f "$file")"
        s="$s file-size=$(stat --printf=%s "$file")"
        s="$s file-mtime=$(printf "%q" "$(stat --printf=%y "$file")")"
    fi
    s="$s $(printf "%q" "$arg")"
done
echo "$s" >> "$HOME/.ln/audacious/$(date +"%Y-%m-%d").log"
