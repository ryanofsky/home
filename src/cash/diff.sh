#!/bin/bash

set -e
set -x

T=$(tempfile)
git show HEAD:./russ.db.sql | sqlite3 "$T"
python3.5 -c "import cash; cash.dump('$T')" > "$T.txt"
diff -ru "$T.txt" russ.db.txt | colordiff | less -F -X
test -n "$DEBUG" || rm -v "$T" "$T.txt"
