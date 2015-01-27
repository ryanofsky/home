# /etc/skel/.bashrc
#
# This file is sourced by all *interactive* bash shells on startup,
# including some apparently interactive shells such as scp and rcp
# that can't tolerate any output.  So make sure this doesn't display
# anything or bad things will happen !
export TMPDIR="$HOME/.local/tmp"
export PATH="$HOME/.local/bin:$HOME/russ/src:$HOME/google/src:$HOME/src:$PATH"
export PYTHONPATH="$HOME/russ/src/lib:$HOME/google/src/lib:$HOME/src/lib:$PYTHONPATH"
export EDITOR=vim
umask u=rwx,g=,o=
export LC_COLLATE=C


# Test for an interactive shell.  There is no need to set anything
# past this point for scp and rcp, and it's important to refrain from
# outputting anything in those cases.
if [[ $- != *i* ]] ; then
	# Shell is non-interactive.  Be done now!
	return
fi


# Put your fun stuff here.

# Look for file in parent directories, print relative path.
findup () {
  local UP
  UP=
  while true; do
    if test -e "$UP$1"; then
      echo -n "$UP$1"
      return 0
    elif test "$(cd "$UP."; pwd)" = /; then
      echo -n "$1"
      return 1
    fi
    UP="../$UP"
  done
}

# Look for file in parent directories, and try removing root path components if
# that doesn't work. Print relative path.
findtrunc () {
  local FILE
  local NFILE
  FILE="$1"
  while true; do
    if FILE="$(findup "$FILE")"; then
      echo -n "$FILE"
      return 0
    fi
    NFILE="${FILE#*/}"
    if test "$NFILE" = "$FILE"; then
      echo -n "$1"
      return 1
    fi
    FILE="$NFILE"
  done
}

# Open file in gvim tab, looking for it in parent directories if it doesn't
# exist, and interpreting string after colon as line number to jump to.
v () {
  local FILE
  local LINE
  for ARG in "$@"; do
    FILE="${ARG%%:*}"
    FILE="$(findtrunc "$FILE")"
    LINE="${ARG}:"
    LINE="${LINE#*:}"
    LINE="${LINE%%:*}"
    if [ -n "$LINE" ]; then
      echo gvim --remote-tab +"$LINE" "$FILE"
      gvim --remote-tab +"$LINE" "$FILE"
    else
      echo gvim --remote-tab "$FILE"
      gvim --remote-tab "$FILE"
    fi
  done
}

r () {
  title="Remind Me:"
  message="${@:2}"

  if [[ "${1:0:1}" == "@" ]]
  then
    echo "notify-send -t 1000000 --icon=dialog-information \"$title\" \"$message\"" | at ${1:1}
  else
    sleep $1 && notify-send -t 1000000 --icon=dialog-information "$title" "$message" &
  fi
}

p () {
  r 25m "-"
}
