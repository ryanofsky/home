#!/bin/bash

set -x
set -e


for b in "$@"; do
    merge=$(git config branch.$b.merge)
    remote=$(git config branch.$b.remote)
    git checkout --detach "$b" --
    git commit --allow-empty -m "Trigger"
    git push --force "$remote" "HEAD:$merge"
    git push --force "$remote" "$b"
done
