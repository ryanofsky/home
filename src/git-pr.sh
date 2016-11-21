#!/bin/bash

set -e

EXPORT=
if [ !"$BASE" ]; then BASE=base; fi
BRANCH=$(git symbolic-ref --short HEAD || git rev-parse HEAD)

run() {
    echo $@
    "$@"
}

update() {
  while read COMMIT NAME PATCH STUFF; do
    if test -z "${NAME##|*}"; then
      echo "Skipping $NAME" 1>&2
    elif test -z "$NAME" || test -n "$STUFF"; then
      echo "Skipping $COMMIT $NAME $PATCH $STUFF" 1>&2
    else
      echo "==== $NAME (${PATCH:-base}) $COMMIT ===="
      if test "$NAME" = "$PATCH"; then
        run git checkout "pr/$NAME"
      elif test -n "$PATCH"; then
        run git checkout -B "pr/$NAME" "pr/$PATCH"
        run git config branch."pr/$NAME".base "pr/$PATCH"
      else
        run git checkout -B "pr/$NAME" "$BASE"
      fi

      # Based on https://github.com/dingram/git-scripts/blob/master/scripts/git-cherry-pick-with-committer
      export GIT_AUTHOR_NAME="$(git log -1 --pretty=format:%an $COMMIT)"
      export GIT_AUTHOR_EMAIL="$(git log -1 --pretty=format:%ae $COMMIT)"
      export GIT_AUTHOR_DATE="$(git log -1 --pretty=format:%ad $COMMIT)"
      export GIT_COMMITTER_NAME="$(git log -1 --pretty=format:%cn $COMMIT)"
      export GIT_COMMITTER_EMAIL="$(git log -1 --pretty=format:%ce $COMMIT)"
      export GIT_COMMITTER_DATE="$(git log -1 --pretty=format:%cd $COMMIT)"
      # Don't care about committer date.
      export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
      # Try to push past failure. Useful with:
      #   git config --global rerere.enabled true
      #   git config --global rerere.autoupdate true
      run git cherry-pick --no-commit "$COMMIT" || true
      run git commit -m"$(git log -1 --pretty=format:%b $COMMIT)"
    fi
  done
  run git checkout $BRANCH
}

CMD=update
VERBOSE=
while test -n "$1"; do
  case "$1" in
   --verbose|-v)
      VERBOSE=1
      ;;
   --list|-l)
      CMD=cat
      ;;
   -*)
      echo "Unknown option '$1'" 1>&2
      exit 1
      ;;
   *)
     break
     ;;
  esac
  shift
done

test "$CMD" != update || git-isclean.sh || exit 1
(git log --format=format:'%H %s' --reverse "$BASE..$BRANCH"; echo) | sed 's/#.*//' | $CMD
