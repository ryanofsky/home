#!/bin/bash

set -e
set -x

IN_MYPAY=~/store/statements/income/2015-12-31-google.html
IN_CHASE=~/store/statements/chase-7165
IN_PAYPAL=~/store/statements/paypal
IN_CITI=~/store/statements/citi-6842

SQL_FILE=russ/cash/russ.db.sql

CHASE_PDF_COMMIT=dee82671
MYPAY_COMMIT=816ae5b0
CHASE_MEMO_COMMIT=2cb84985
CHASE_CSV_COMMIT=70de74e7
PAYPAL_COMMIT=6f2a55af
CITI_COMMIT=7aed73e1

set -x

dump() {
    local src="$1"
    local dst="$2"

    if [ -n "$src" ]; then
        if [ -e "test/$src.expected.sql" ]; then
            cp -afv "test/$src.expected.sql" "_test/$dst.sql"
        else
            git show "$src:$SQL_FILE" >  "_test/$dst.sql"
        fi
        rm -fv _test.db
        sqlite3 _test.db < "_test/$dst.sql"
     else
        sqlite3 _test.db <<< ".dump" > "_test/$dst.sql"
     fi
     python3.5 -c "import cash; cash.dump('_test.db')" > "_test/$dst.txt"
}

compare () {
    diff -u "$1" "$2"| colordiff >&2
    fail=${PIPESTATUS[0]}
    if [ "$fail" != 0 ]; then
        echo "Diff failed (status $fail, $1 $2)."
        exit 1
    fi
}

run() {
    local name="$1"
    local expected="$2"
    local input="$3"
    local cmd="$4"
    if test -z "$expected"; then expected="$name"; fi

    mkdir -p _test
    dump "$expected" "$name.expected"
    dump "$input"    "$name.input"
    python3.5 -c "import cash; $cmd"
    dump ""          "$name.output"
    compare "_test/$name.expected.txt" "_test/$name.output.txt"
    compare "_test/$name.expected.sql" "_test/$name.output.sql"
}

run 1-chase-pdf  "$CHASE_PDF_COMMIT"  "$CHASE_PDF_COMMIT^"  "cash.import_chase_txns('1-chase-data', '_test.db')"
run 2-mypay      "$MYPAY_COMMIT"      "$MYPAY_COMMIT^"      "cash.import_pay_txns('$IN_MYPAY', '_test.db')"
run 3-chase-memo "$CHASE_MEMO_COMMIT" "$CHASE_MEMO_COMMIT^" "cash.update_chase_memos('_test.db')"
run 4-chase-csv  "$CHASE_CSV_COMMIT"  "$CHASE_CSV_COMMIT^"  "cash.import_chase_update('$IN_CHASE/2016-01-30.csv', '_test.db'); cash.import_chase_update('$IN_CHASE/2016-03-08.csv', '_test.db')"
run 5-paypal     "$PAYPAL_COMMIT"     "$PAYPAL_COMMIT^"     "cash.import_paypal_csv('$IN_PAYPAL', '_test.db')"
run 6-citi       "$CITI_COMMIT"       "$CITI_COMMIT^"       "cash.import_citi_tsv('$IN_CITI/2016-03-01.tsv', '_test.db')"

python3.5 -c "import cash; cash.test_parse_yearless_dates()"

echo Tests pass
