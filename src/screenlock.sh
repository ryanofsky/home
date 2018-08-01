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

handle-gnome-check() {
    # https://askubuntu.com/questions/505681/gnome-how-to-detect-if-the-screen-is-locked
    OUT=$(gdbus call -e -d org.gnome.ScreenSaver -o /org/gnome/ScreenSaver -m org.gnome.ScreenSaver.GetActive)
    if [ "$OUT" = "(true,)" ]; then
        exit 0
    elif [ "$OUT" = "(false,)" ]; then
        exit 1
    else
        echo "Bad output '$OUT'"
        exit 2
    fi
}

handle-gnome-lock() {
    gdbus call -e -d org.gnome.ScreenSaver -o /org/gnome/ScreenSaver -m org.gnome.ScreenSaver.Lock
    exit $?
}

idle-str() {
    local idle=$(xprintidle)
    local min=$((idle/60000))
    local ms=$((idle%60000))
    printf "%s (%dm %d.%03ds)" "$idle" "$min" "$((ms/1000))" "$((ms%1000))"
}

handle-locked() {
    echo "$(date) -- locked idle $(idle-str)" | tee -a ~/work/logbook
}

handle-unlocked() {
    echo "$(date) -- unlocked idle $(idle-str)" | tee -a ~/work/logbook
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

handle-gnome-monitor() {
    # https://unix.stackexchange.com/questions/28181/run-script-on-screen-lock-unlock
    dbus-monitor --session "type='signal',interface='org.gnome.ScreenSaver'" |
        while read line; do
            case "$line" in
                *"path=/org/gnome/ScreenSaver; interface=org.gnome.ScreenSaver; member=ActiveChanged")
                    read line
                    if [ "$line" = "boolean false" ]; then handle-unlocked;
                    elif [ "$line" = "boolean true" ]; then handle-locked;
                    else echo "Bad line '$line'"; exit 1; fi
                ;;
            esac
        done
}

if [ "$XDG_CURRENT_DESKTOP" = GNOME ] || [ "$XDG_CURRENT_DESKTOP" = ubuntu:GNOME ]; then
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
