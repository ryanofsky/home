#!/bin/bash

FIFO="$TMPDIR/pom.d"
TIMEOUT=300

popup() {
    e -c $(readlink -f "$HOME/.ln/todo.org")
}

if [ "$1" = monitor ]; then
    mkfifo "$FIFO"
    exec 3<>"$FIFO"
    TIMEOUTS=0
    while true; do
        if read -u 3 -t "$TIMEOUT" T; then
            echo "$(date) -- sleep $T"
            sleep $T
            echo "$(date) -- popup"
            popup
            TIMEOUTS=0
            continue
        fi

        if screenlock.sh check; then
            TIMEOUTS=0
            continue
        fi

        ((++TIMEOUTS))

        if [ "$TIMEOUTS" -lt 5 ]; then
            echo "$(date) -- popup ($TIMEOUTS timeouts)"
            popup
        else
            echo "$(date) -- lock ($TIMEOUTS timeouts)"
            screenlock.sh lock
        fi
    done
else
    T=${1:-25m}
    echo "$T" >> $TMPDIR/pom.d
fi
