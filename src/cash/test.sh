#!/bin/bash

set -e

IN_PAY=~/store/statements/income/2015-12-31-google.html
CHASE_COMMIT=dee82671
PAY_COMMIT=816ae5b0
SQL_FILE=russ/cash/russ.db.sql
CHASE_MERGE_CMD="cash.import_chase_update('/home/russ/store/statements/chase-7165/2016-01-30.csv','_test.db', disable_memo_merge=True)"
for i in 1-chase-data/*.json; do
    if [ "$i" \> 1-chase-data/2014 ]; then
        CHASE_MERGE_CMD="$CHASE_MERGE_CMD
cash.import_chase_update('$i', '_test.db')
"
    fi
done

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

run 8-clean          ""              "7-citi"         "cash.cleanup('_test.db')"
exit

run 1-chase          "$CHASE_COMMIT" "$CHASE_COMMIT^" "cash.import_chase_txns('1-chase-data', '_test.db')"
run 2-mypay          "$PAY_COMMIT"   "$PAY_COMMIT^"   "cash.import_pay_txns('$IN_PAY', '_test.db')"
run 3-chase-memos    ""              "HEAD"           "cash.update_chase_memos('_test.db')"
run 4-chase-0130     ""              "3-chase-memos"  "cash.import_chase_update('/home/russ/store/statements/chase-7165/2016-01-30.csv','_test.db')"
run 5-chase-0308     ""              "4-chase-0130"   "cash.import_chase_update('/home/russ/store/statements/chase-7165/2016-03-08.csv','_test.db')"
run 6-paypal         ""              "5-chase-0308"   "cash.import_paypal_csv('/home/russ/store/statements/paypal','_test.db')"
run 7-citi           ""              "6-paypal"       "cash.import_citi_tsv('/home/russ/store/statements/citi-6842/2016-03-01.tsv','_test.db')"

run 4.1-chase-merge "4-chase-0130"   "3-chase-memos"  "$CHASE_MERGE_CMD"
python3.5 -c "import cash; cash.test_parse_yearless_dates()"

echo Tests pass
