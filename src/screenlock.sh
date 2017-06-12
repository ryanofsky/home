#!/bin/bash

handle-unity-check() {
    # https://askubuntu.com/questions/505681/unity-how-to-detect-if-the-screen-is-locked
    OUT=$(gdbus call -e -d com.canonical.Unity -o /com/canonical/Unity/Session -m com.canonical.Unity.Session.IsLocked)
    if [ "$OUT" = "(true,)" ]; then
        exit 0
    elif [ "$OUT" = "(false,)" ]; then
        exit 1
    else
        echo "Bad output '$OUT'"
        exit 2
    fi
}

handle-unity-lock() {
    qdbus com.canonical.Unity /com/canonical/Unity/Session com.canonical.Unity.Session.Lock
    exit $?
}

handle-locked() {
    echo "$(date) -- locked"
}

handle-unlocked() {
    echo "$(date) -- unlocked"
}

handle-unity-monitor() {
    # https://unix.stackexchange.com/questions/28181/run-script-on-screen-lock-unlock
    dbus-monitor --session "type='signal',interface='com.canonical.Unity.Session'" |
        while read line; do
            case "$line" in
                *"; member=Locked") handle-locked;;
                *"; member=Unlocked") handle-unlocked;;
            esac
        done
    # signal time=1497302025.510647 sender=:1.44 -> destination=(null destination) serial=130094 path=/com/canonical/Unity/Session; interface=com.canonical.Unity.Session; member=Locked
    # signal time=1497302029.114925 sender=:1.44 -> destination=(null destination) serial=130117 path=/com/canonical/Unity/Session; interface=com.canonical.Unity.Session; member=Unlocked
}

if [ "$XDG_CURRENT_DESKTOP" = GNOME ]; then
    DESKTOP=gnome
elif [ "$XDG_CURRENT_DESKTOP" = Unity ]; then
    DESKTOP=unity
else
    echo "Bad desktop '$XDG_CURRENT_DESKTOP'"
    exit 1
fi

CMD="$1"
shift
"handle-${DESKTOP}-${CMD}" "$@"
