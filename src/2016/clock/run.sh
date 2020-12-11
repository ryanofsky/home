#!/usr/bin/env bash

set -x
set -e

rm -rvf "Anthony Burgess - A Clockwork Orange sub.epub" 0
unzip -d 0 ~/pia/Incoming/"Anthony Burgess - A Clockwork Orange.epub"
python gloss.py
cd 0
zip -r ../idk.zip .
cd ..
rm -rf 0
mv idk.zip "Anthony Burgess - A Clockwork Orange sub.epub"
ebook-viewer "Anthony Burgess - A Clockwork Orange sub.epub" &
