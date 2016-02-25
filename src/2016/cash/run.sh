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

# rm -rf 0-chase-txt
if [ ! -e 0-chase-txt ]; then
    mkdir 0-chase-txt

    (cd pdfminer; python setup.py build)

    for i in "$IN_CHASE"/*.pdf; do
        o="${i#$IN_CHASE/}"
        o="${o%.pdf}"
        pdfminer/build/scripts-2.7/pdf2txt.py "$i" > 0-chase-txt/"$o.json"
    done
fi

# rm -rf 1-chase-data
if [ ! -e 1-chase-data ]; then
    mkdir 1-chase-data
    python3.5 -c '
import cash, json
cash.dump_chase_txns("0-chase-txt/2005-10-20.json",
                     "1-chase-data/2005-10-20.json",
                     "1-chase-data/2005-10-20.discard")
cash.dump_chase_txns("0-chase-txt/2014-07-18.json",
                     "1-chase-data/2014-07-18.json",
                     "1-chase-data/2014-07-18.discard")
'

  test-eq 1-chase-data/2005-10-20.json expected-1-chase-data-2005-10-20.json
  test-eq 1-chase-data/2005-10-20.discard expected-1-chase-data-2005-10-20.discard
  test-eq 1-chase-data/2014-07-18.json expected-1-chase-data-2014-07-18.json
  test-eq 1-chase-data/2014-07-18.discard expected-1-chase-data-2014-07-18.discard
fi

# rm -rf 9-mypay-data
if [ ! -e 9-mypay-data ]; then
    mkdir 9-mypay-data

    python3.5 -c '
import cash
cash.parse_mypay_html("mypay.html")
' > 9-mypay-data/txt

  test-eq 9-mypay-data/txt expected-9-mypay-data.txt
fi
