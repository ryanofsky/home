#!/bin/bash

set -e
set -x

IN_PAY=~/store/statements/income/2015-12-31-google.html

CHASE_COMMIT=dee82671
PAY_COMMIT=816ae5b0
SQL_FILE=russ/cash/russ.db.sql

run() {
    test ! -e _test.db || rm -vi _test.db
    git show "$1^:$SQL_FILE" | sqlite3 _test.db
    trap "rm -f _test.db" EXIT
    python3.5 -c "import cash"$'\n'"$2"
    fail=
    if ! diff -u <(sqlite3 _test.db <<< ".dump") <(git show "$1:$SQL_FILE"); then
        exit 1
    fi
    rm _test.db
}

run "$CHASE_COMMIT" "cash.import_chase_txns('1-chase-data', '_test.db')"
run "$PAY_COMMIT" "cash.import_pay_txns('$IN_PAY', '_test.db')"
echo Tests pass
