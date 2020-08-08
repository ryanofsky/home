# /etc/skel/.bashrc
#
# This file is sourced by all *interactive* bash shells on startup,
# including some apparently interactive shells such as scp and rcp
# that can't tolerate any output.  So make sure this doesn't display
# anything or bad things will happen !
export TMPDIR="$HOME/.local/tmp"
export PATH="$HOME/.local/bin:$HOME/russ/src:$HOME/google/src:$HOME/src:$HOME/.npm-global/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"
export PYTHONPATH="$HOME/russ/src/lib:$HOME/google/src/lib:$HOME/src/lib:$PYTHONPATH"
export EDITOR=vim
umask u=rwx,g=,o=
export LC_COLLATE=C

if tty -s; then
  export GPG_TTY=$(tty)
fi

if [ -e "$HOME/.ln/bashrc" ]; then
  . "$HOME/.ln/bashrc"
fi

# Test for an interactive shell.  There is no need to set anything
# past this point for scp and rcp, and it's important to refrain from
# outputting anything in those cases.
if [[ $- != *i* ]] ; then
	# Shell is non-interactive.  Be done now!
	return
fi


# Put your fun stuff here.

et() {
    emacsclient -t "$@"
}

# dump emacsclient kill buffer
ekill() {
    python -c "print($(emacsclient -e '(substring-no-properties (car kill-ring))'))"
}

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

# https://www.reddit.com/r/spacemacs/comments/544rdw/vimdiff_or_diffthis_in_spacemacs/d7z9aao/
# https://gist.github.com/tasmo/c6bd7576f7f090a9c206099cf88a58d9
function ediff () {
    if [ "X${2}" = "X" ]; then
        echo "USAGE: ediff <FILE 1> <FILE 2>"
    else
        quoted1=${1//\\/\\\\}; quoted1=${quoted1//\"/\\\"}
        quoted2=${2//\\/\\\\}; quoted2=${quoted2//\"/\\\"}
        emacsclient -tc -a emacs -e "(ediff \"$quoted1\" \"$quoted2\")"
    fi
}

# https://unix.stackexchange.com/questions/76628/gnu-screen-weird-characters-on-click
fm() {
    printf '\033[?9l'
}
