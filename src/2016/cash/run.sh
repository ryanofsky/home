#!/bin/bash

set -e
set -x

IN_CHASE=~/store/statements/chase-7165

test-eq() {
    if ! cmp "$1" "$2"; then
        echo "Bad output $1 $2" 2>&1
        exit 1
    fi
}

if [ ! -e 0-chase-txt ]; then
    mkdir 0-chase-txt

    (cd pdfminer; python setup.py build)

    for i in "$IN_CHASE"/*.pdf; do
        o="${i#$IN_CHASE/}"
        o="${o%.pdf}"
        pdfminer/build/scripts-2.7/pdf2txt.py "$i" > 0-chase-txt/"$o.json"
    done
fi

rm -rf 1-chase-data
if [ ! -e 1-chase-data ]; then
    mkdir 1-chase-data

    python3.5 -c '
import cash, json
txns, _, _, _ = cash.parse_chase_pdftext("0-chase-txt/2014-07-18.json")
with open("1-chase-data/2014-07-18.json", "w") as fp:
  json.dump([(txn.balance, txn.amount, txn.debit, txn.info) for txn in txns],
            fp, sort_keys=True, indent=4)
'

  test-eq 1-chase-data/2014-07-18.json expected-1-chase-data-2014-07-18.json
fi
