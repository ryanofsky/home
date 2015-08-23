#!/bin/sh

# http://stackoverflow.com/questions/7348698/git-how-to-list-all-objects-in-the-database

set -e

# Find all the objects that are in packs:

find objects/pack -name 'pack-*.idx' | while read p ; do
    git show-index < $p | cut -f 2 -d ' '
done

# And now find all loose objects:
find objects/ | sed -n 's,objects/\([0-9a-f]\{2\}\)/\([0-9a-f]\{38\}\),\1\2,p'
