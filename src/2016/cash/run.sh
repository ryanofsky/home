#!/bin/bash

set -e
set -x

IN_CHASE=~/store/statements/chase-7165
CASH_DB=~/russ/cash/russ.db

mkdir -p 0-chase-txt 1-chase-data 2-chase-imported

(cd pdfminer; python setup.py build)

for i in "$IN_CHASE"/*.pdf; do
    o="0-chase-txt/${i#$IN_CHASE/}"
    o="${o%.pdf}.json"
    if [ ! -e "$o" ]; then
        pdfminer/build/scripts-2.7/pdf2txt.py "$i" > "$o"
    fi
done

for i in 0-chase-txt/*.json; do
    o="1-chase-data/${i#0-chase-txt/}"
    if [ ! -e "$o" ]; then
        python3.5 -c "import cash; cash.dump_chase_txns('$i', '$o', '$o.discard')"
    fi
done

python3.5 -c "import cash; cash.update_chase_memos('$CASH_DB')"

for i in 1-chase-data/*.json; do
    o="2-chase-imported/${i#1-chase-data/}"
    o="${o%.json}.pdf"
    if [ ! -e "$o" ]; then
        python3.5 -c "import cash; cash.import_chase_update('$i', '$CASH_DB')"
        touch "$o"
    fi
done

for i in "$IN_CHASE"/*.csv; do
    o="2-chase-imported/${i#$IN_CHASE/}"
    if [ ! -e "$o" ]; then
        python3.5 -c "import cash; cash.import_chase_update('$i', '$CASH_DB')"
        touch "$o"
    fi
done
