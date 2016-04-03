#!/bin/bash
# from http://stackoverflow.com/questions/12339165/how-to-pack-all-loose-objects-in-git
set -e
set -x
# Repacking disabled by default, makes incremental backup more cumbersome.
test -z "$REPACK" || git gc --no-prune
git prune-packed
find .git/objects/?? -type f | perl -pe 's@^\.git/objects/(..)/@$1@' | git pack-objects .git/objects/pack/pack
git prune-packed
