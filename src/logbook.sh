#!/bin/bash

prev=
while read weekday month day time tz year rest; do
    date=$(date --date="$weekday $month $day $time $tz $year" '+%Y-%m-%d %a %H:%M')
    echo "CLOCK: [${prev:-$date}]--[$date] => 0:00"
    echo "- $rest"
    prev="$date"
done < ~/.ln/org/date

if [ "$1" = 1 ]; then
    mv ~/.ln/org/date{,.old}
fi
