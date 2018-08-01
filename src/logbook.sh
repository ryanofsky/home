#!/bin/bash

prev=
while read weekday month day time tz year rest; do
    date=$(date --date="$weekday $month $day $time $tz $year" '+%Y-%m-%d %a %H:%M')
    test "$prev" = "$date" || echo "CLOCK: [${prev:-$date}]--[$date] =>  0:00"
    echo "- $rest"
    prev="$date"
done < ~/work/logbook

if [ "$1" = 1 ]; then
    mv ~/work/logbook{,.old}
fi
