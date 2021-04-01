#!/usr/bin/env bash

prev=
while read line; do
    date="${line%% -- *}"
    rest="${line#* -- }"
    date=$(date --date="$date" '+%Y-%m-%d %a %H:%M')
    dsec=$(date --date="$date" '+%s')
    sec=$((dsec-psec))
    min=$((sec/60))
    sec=$((sec%60))
    hour=$((min/60))
    min=$((min%60))
    dur=$(printf "%2d:%02d" "$hour" "$min")
    test "$prev" = "$date" || echo "CLOCK: [${prev:-$date}]--[$date] => $dur"
    echo "- $rest"
    prev="$date"
    psec="$dsec"
done < ~/work/logbook/logbook

mv --backup=numbered ~/work/logbook/logbook ~/work/logbook/logbook.prev
