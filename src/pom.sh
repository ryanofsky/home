#!/bin/bash

FIFO="$TMPDIR/pom.d"
TIMEOUT=300
#export TZ=WET
#export TZ=CET
export TZ=Asia/Tokyo

popup() {
    if test "$1" != 0; then while test $(xprintidle) -lt 2000; do sleep 1; done; fi
    echo "$(date) -- emacsclient"
    e -c $(readlink -f "$HOME/.ln/org")/todo.org
}

if [ "$1" = monitor ]; then
    mkfifo "$FIFO"
    exec 3<>"$FIFO"
    TIMEOUTS=0 # number of timeouts
    DUR=$TIMEOUT
    while true; do
        if read -u 3 -t "$DUR" T; then
            DUR=$(sed s/m/*60/ <<<"$T" | bc)
            echo "$(date) -- sleep $T ($DUR)"
            TIMEOUTS=0
            continue
        fi

        if screenlock.sh check; then
            TIMEOUTS=0
        elif [ "$TIMEOUTS" -lt 4 ]; then
            echo "$(date) -- popup ($TIMEOUTS timeouts)"
            popup "$DUR"
        else
            echo "$(date) -- lock ($TIMEOUTS timeouts)"
            screenlock.sh lock
        fi

        DUR=$TIMEOUT
        ((++TIMEOUTS))
    done
else
    T=25m
    if [[ "$1" =~ ^[0-9] ]]; then
        T="$1"
        shift
    fi
    echo "$(date) pom $T $@" | tee -a ~/work/logbook
    echo "$T" >> $TMPDIR/pom.d
fi
