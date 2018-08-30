#!/bin/bash

prev=
while read weekday month day time tz year rest; do
    date=$(date --date="$weekday $month $day $time $tz $year" '+%Y-%m-%d %a %H:%M')
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
done < ~/work/logbook

if [ "$1" = 1 ]; then
    mv ~/work/logbook{,.old}
fi
