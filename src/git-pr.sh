#!/bin/bash

set -e

EXPORT=
if [ -z "$BASE" ]; then BASE=$(git rev-list --min-parents=2 --max-count=1 HEAD); fi
if [ -z "$XBASE" ]; then XBASE="$BASE"; fi
BRANCH=$(git symbolic-ref --short HEAD || git rev-parse HEAD)

run() {
    echo $@
    "$@"
}

update() {
    if [ "$#" != 1 ]; then
        >&2 echo "Error: bad update arguments '$@'"
        exit 1
    fi

    local want="$1"
    local first=1

    while read COMMIT SUBJ; do
        if test -z "${SUBJ##|*}"; then
            echo "Skipping $SUBJ" 1>&2
            continue
        fi

        local name="${SUBJ%% *}"
        local rest="${SUBJ#* }"
        local fixup=
        if [ "$name" = "fixup!" ]; then
             fixup=1
             name="${rest%% *}"
             rest="${rest#* }"
        fi

        merge="${rest%% *}"
        rest="${rest#* }"
        if [ "$merge" = "#" ]; then
             merge=
        else
            if [ "$merge" = "$name" ]; then
                merge=
            fi
            pound="${rest%% *}"
            rest="${rest#* }"
            if [ "$pound" != "#" ]; then
                 echo "Skipping bad $SUBJ" 1>&2
                 continue
            fi
        fi

        # split name on + to check for commits that belong to multiple prs
        # check for trailing ^ on pr name to check for commits that should be squashed
        local found=
        local squash=
        for n in ${name/+/ } ; do
            if [ "${n%^}" = "$want" ]; then
                found=1
                if [ -z "${n#*^}" ]; then
                    squash=1
                fi
                break
            fi
        done

        if [ -z "$found" ]; then
            continue
        fi

        if [ -n "$first" ]; then
            first=
            if ! git rev-parse --verify "pr/$name"; then
                run git branch "pr/$name" "$XBASE"
                RESET=1
            fi
            run git checkout "pr/$name"
            if [ -z "$RESET" ]; then
                run git reset --hard $(git rev-list --min-parents=2 --max-count=1 HEAD)
            else
                run git reset --hard "$XBASE"
                local m
                for m in ${merge/+/ } ; do
                    export GIT_AUTHOR_DATE="$(git log -1 --pretty=format:%ad "pr/$m" --date=raw)"
                    export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
                    run git merge --no-ff --no-edit "pr/$m"
                done
            fi
            run git config "branch.pr/$name.export" "$BRANCH"
        fi

        echo "==== $COMMIT name=$name merge=$merge fixup=$fixup squash=$squash rest='$rest' ===="

        local metacommit=$COMMIT
        if [ -n "$squash" ]; then
            if [ -n "$first" ]; then
                # Could be implemented in future by squashing into following
                echo "Squashing first commit not implemented"
                exit 1
            fi
           metacommit=HEAD
        fi

        # Based on https://github.com/dingram/git-scripts/blob/master/scripts/git-cherry-pick-with-committer
        export GIT_AUTHOR_NAME="$(git log -1 --pretty=format:%an $metacommit)"
        export GIT_AUTHOR_EMAIL="$(git log -1 --pretty=format:%ae $metacommit)"
        export GIT_AUTHOR_DATE="$(git log -1 --pretty=format:%ad $metacommit --date=raw)"
        export GIT_COMMITTER_NAME="$(git log -1 --pretty=format:%cn $metacommit)"
        export GIT_COMMITTER_EMAIL="$(git log -1 --pretty=format:%ce $metacommit)"
        export GIT_COMMITTER_DATE="$(git log -1 --pretty=format:%cd $metacommit --date=raw)"
        # Discard committer info.
        export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
        export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
        export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

        # Use monotonic timestamps so github branch commit lists are readable.
        read NEW_TIMESTAMP NEW_TZ <<<"$GIT_COMMITTER_DATE"
        read PREV_TIMESTAMP PREV_TZ <<<$(git log -1 --pretty=format:%cd --date=raw)
        if (($NEW_TIMESTAMP < $PREV_TIMESTAMP)); then
            GIT_COMMITTER_DATE="$PREV_TIMESTAMP $NEW_TZ"
        fi
        # Try to push past failure. Useful with:
        #   git config --global rerere.enabled true
        #   git config --global rerere.autoupdate true
        run git cherry-pick --no-commit "$COMMIT" || true
        if [ -e "$(git rev-parse --git-dir)/index.lock" ]; then
            echo "(((((((((((sleep to avoid index.lock fs race)))))))))))"
            sleep 1
        fi
        local fix=
        if [ -n "$fixup" ]; then
            fix="fixup! $rest"$'\n'$'\n'
        fi
        if [ -n "$squash" ]; then
            run git commit --amend --no-edit
        else
            run git commit -m"$fix$(git log -1 --pretty=format:%b $COMMIT)"
        fi
    done < <(git log --format=format:'%H %s' --reverse "$BASE..$BRANCH" && echo)
    run git checkout $BRANCH
    echo "== Successfully exported branch pr/$want =="
    echo "ppush pr/$want"
}

RESET=
while test -n "$1"; do
  case "$1" in
    --reset|-r)
      RESET=1
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

if [ "$#" = 0 ]; then
    git log --format=format:'%H %s' --reverse "$BASE..$BRANCH"
    exit 0
fi

git-isclean.sh || exit 1

update "$@"
