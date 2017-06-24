#!/bin/bash

FIFO="$TMPDIR/pom.d"
TIMEOUT=300

popup() {
    e -c $(readlink -f "$HOME/.ln/todo.org")
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
            popup
        else
            echo "$(date) -- lock ($TIMEOUTS timeouts)"
            screenlock.sh lock
        fi

        DUR=$TIMEOUT
        ((++TIMEOUTS))
    done
else
    T=${1:-25m}
    echo "$T" >> $TMPDIR/pom.d
fi
