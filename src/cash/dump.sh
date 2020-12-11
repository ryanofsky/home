#!/usr/bin/env bash

set -e
set -x

sqlite3 russ.db <<< ".dump" > russ.db.sql
python3 -c "import cash; cash.dump('russ.db')" > russ.db.txt
