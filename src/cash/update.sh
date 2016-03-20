#!/bin/bash

set -e
set -x

IN_CHASE=~/store/statements/chase-7165

if [ ! -e pdfminer ]; then
    git clone https://github.com/euske/pdfminer.git
    ( cd pdfminer; git apply ) < pdfminer.diff
    ( cd pdfminer; python setup.py build )
fi

mkdir -p 0-chase-txt 1-chase-data 2-chase-imported

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

for i in 1-chase-data/*.json; do
    o="2-chase-imported/${i#1-chase-data/}"
    o="${o%.json}.pdf"
    if [ ! -e "$o" ]; then
        python3.5 -c "import cash; cash.import_chase_update('$i', 'russ.db')"
        touch "$o"
    fi
done

for i in "$IN_CHASE"/*.csv; do
    o="2-chase-imported/${i#$IN_CHASE/}"
    if [ ! -e "$o" ]; then
        python3.5 -c "import cash; cash.import_chase_update('$i', 'russ.db')"
        touch "$o"
    fi
done
