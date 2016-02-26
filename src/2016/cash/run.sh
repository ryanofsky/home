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
import cash, os
for filename in os.listdir("0-chase-txt"):
    assert filename.endswith(".json")
    if filename >= "2006-09-21.json" and filename <= "2007-01-19.json":
        print("SKIP == {} ==".format(filename))
        continue
    if filename >= "2007-02-20.json" and filename <= "2007-08-17.json":
        print("SKIP == {} ==".format(filename))
        continue
    print("== {} ==".format(filename))
    pdftext_input_json_filename = os.path.join("0-chase-txt", filename)
    txns_output_json_filename = os.path.join("1-chase-data", filename)
    discarded_text_output_filename = txns_output_json_filename[:-5] + ".discard"
    cash.dump_chase_txns(pdftext_input_json_filename,
                        txns_output_json_filename,
                        discarded_text_output_filename)
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
