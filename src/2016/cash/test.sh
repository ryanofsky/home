#!/bin/bash

set -e
set -x

IN_PAY=~/store/statements/income/2015-12-31-google.html

CHASE_COMMIT=dee82671
PAY_COMMIT=816ae5b0
SQL_FILE=russ/cash/russ.db.sql

setup() {
    rm -fv _test.db
    trap "rm -fv _test.db" EXIT
    if [ "$1" = commit ]; then
        git show "$2:$SQL_FILE" | sqlite3 _test.db
    else
        sqlite3 _test.db < "$2"
    fi
}

run() {
    python3.5 -c "import cash; $3"
    test -z "$DEBUG" || sqlite3 _test.db <<< ".dump" > _test.db.sql
    if [ "$1" = commit ]; then
        diff -u <(git show "$2:$SQL_FILE") <(sqlite3 _test.db <<< ".dump")
    else
        diff -u "$2" <(sqlite3 _test.db <<< ".dump")
    fi | colordiff
    fail=${PIPESTATUS[0]}
    if [ "$fail" != 0 ]; then
        echo "Diff failed (status $fail)."
        exit 1
    fi
}

setup commit "$CHASE_COMMIT^"
run   commit "$CHASE_COMMIT" "cash.import_chase_txns('1-chase-data', '_test.db')"

setup commit "$PAY_COMMIT^"
run   commit "$PAY_COMMIT" "cash.import_pay_txns('$IN_PAY', '_test.db')"

setup commit "HEAD"
run   file   expected-chase-memos.db.sql "cash.update_chase_memos('_test.db')"

setup file   expected-chase-memos.db.sql
run   file   expected-chase-csv1.db.sql "cash.import_chase_update('/home/russ/store/statements/chase-7165/2016-01-30.csv','_test.db')"

setup file   expected-chase-csv1.db.sql
run   file   expected-chase-csv2.db.sql "cash.import_chase_update('/home/russ/store/statements/chase-7165/2016-03-08.csv','_test.db')"

python3.5 -c "import cash; cash.test_parse_yearless_dates()"

set +x
CMD="cash.import_chase_update('/home/russ/store/statements/chase-7165/2016-01-30.csv','_test.db', disable_memo_merge=True)"
for i in 1-chase-data/*.json; do
    if [ "$i" \> 1-chase-data/2014 ]; then
        CMD="$CMD
cash.import_chase_update('$i', '_test.db')
"
    fi
done
set -x
setup file   expected-chase-memos.db.sql
run   file   expected-chase-csv1.db.sql "$CMD"

setup file   expected-chase-memos.db.sql
run   file   expected-chase-memos.db.sql "cash.import_paypal_csv('/home/russ/store/statements/paypal','_test.db')" > _test.out.txt
if ! diff -q  expected-paypal.txt _test.out.txt; then
   diff -u expected-paypal.txt _test.out.txt | colordiff
   echo Fail
   exit 1
fi

echo Tests pass
