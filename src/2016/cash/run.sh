#!/bin/bash

set -e
set -x

IN_CHASE=~/store/statements/chase-7165
CASH_DB=~/russ/cash/russ.db

mkdir -p 0-chase-txt 1-chase-data

(cd pdfminer; python setup.py build)

for i in "$IN_CHASE"/*.pdf; do
o="0-chase-txt/${i#$IN_CHASE/}"
o="${o%.pdf}.json"
if [ ! -e "$o" ]; then
    pdfminer/build/scripts-2.7/pdf2txt.py "$i" > "$o"
fi
done

python3.5 -c '
import cash, os
for filename in os.listdir("0-chase-txt"):
    assert filename.endswith(".json")
    pdftext_input_json_filename = os.path.join("0-chase-txt", filename)
    txns_output_json_filename = os.path.join("1-chase-data", filename)
    if os.path.exists(txns_output_json_filename):
        continue
    print("== {} ==".format(filename))
    discarded_text_output_filename = txns_output_json_filename[:-5] + ".discard"
    cash.dump_chase_txns(pdftext_input_json_filename,
                        txns_output_json_filename,
                        discarded_text_output_filename)
'
