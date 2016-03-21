#!/bin/bash

set -e
set -x

git checkout HEAD russ.db.sql
yes | ./load.sh
python3.5 -c "import cash; cash.cleanup2('russ.db')"
./dump.sh
diff -ru russ.db.txt.expected russ.db.txt | colordiff | less -F -X
fail=${PIPESTATUS[0]}
if [ "$fail" = 0 ]; then
    echo No changes.
else
    cp -aiv russ.db.txt russ.db.txt.expected
fi












