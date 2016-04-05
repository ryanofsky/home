#!/bin/bash

set -e
set -x

for f in "$@"; do
    if test -e "$f.upstream"; then
        rm -fv "$f"
    else
        if test -e "$f"; then
            mv -iv "$f" "$f.upstream"
        else
            touch "$f.upstream"
        fi
    fi
done
