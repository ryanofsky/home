#!/usr/bin/env bash

set -e

EXPORT=
if [ -z "$BASE" ]; then BASE=$(git rev-list --min-parents=2 --max-count=1 HEAD); fi
if [ -z "$XBASE" ]; then XBASE="$BASE"; fi
BRANCH=$(git symbolic-ref --short HEAD || git rev-parse HEAD)
if [ "$BASE" = orphan ]; then SPAN="$BRANCH"; else SPAN="$BASE..$BRANCH"; fi

. ~/src/pr.sh

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
    local committed=
    declare -A patched

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
        local revert=
        if [ "$name" = "Revert" ]; then
             revert=1
             name="${rest%% *}"
             name="${name#\"}"
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

        local desc="${rest//\//-}"

        # split name on + to check for commits that belong to multiple prs
        # trailing ^ on pr name means squash into previous commit
        # trailing @ on pr name means squash into next commit
        # trailing ^ on first commit dependency name means cherry pick rather than merge
        local found=
        local squash=
        local squash_next=
        for n in $(echo "$name" | sed 's:+: :g'); do
            if [ "${n%^}" = "$want" -o "${n%@}" = "$want"  ]; then
                found=1
                if [ -z "${n#*^}" ]; then
                    squash=1
                fi
                if [ -z "${n#*@}" ]; then
                    squash=1
                    squash_next=1
                fi
                break
            fi
        done

        if [ -z "$found" ]; then
            continue
        fi

        echo "==== $COMMIT name=$name merge=$merge fixup=$fixup revert=$revert squash=$squash desc='$desc' first=$first committed=$committed ===="

        if [ -n "$first" ]; then
            first=
            if ! git rev-parse --verify "pr/$want"; then
                if [ "$XBASE" = orphan ]; then
                    git checkout --orphan "pr/$want"
                else
                    run git branch "pr/$want" "$XBASE"
                    run git checkout "pr/$want"
                    RESET=1
                fi
            else
                run git checkout "pr/$want"
            fi

            if [ -z "$RESET" ]; then
                run git reset --hard $(git rev-list --min-parents=2 --max-count=1 HEAD)
            elif [ "$XBASE" = orphan ]; then
                run git rm -r .
                run rm -fv .git/refs/heads/"pr/$want" .git/index
            else
                run git reset --hard "$XBASE"
            fi

                local m
                for m in $(echo "$merge" | sed 's:+: :g'); do
                    if [ -z "${m#*^}" ]; then
                        merge_source="pr/${m%^}"
                        merge_cherry=1
                    else
                        merge_source="pr/$m"
                        merge_cherry=
                    fi
                    merge_log=
                    prbranch=$(meta-read "refs/heads/$merge_source/.prbranch" | sed s:refs/remotes/:: || true)
                    if [ -n "$prbranch" ]; then
                        merge_log="Merge remote-tracking branch '$prbranch'"
                    fi
                    # Montonic timestamp to unfuck github ordering in branch commits view
                    read NEW_TIMESTAMP NEW_TZ <<<$(git log -1 --pretty=format:%ad --date=raw)
                    read PREV_TIMESTAMP PREV_TZ <<<$(git log -1 --pretty=format:%cd --date=raw)
                    if (($NEW_TIMESTAMP < $PREV_TIMESTAMP)); then
                        NEW_TIMESTAMP="$PREV_TIMESTAMP"
                        NEW_TZ="$PREV_TZ"
                    fi
                    read PREV_TIMESTAMP PREV_TZ <<<$(git log -1 --pretty=format:%ad --date=raw "$merge_source")
                    if (($NEW_TIMESTAMP < $PREV_TIMESTAMP)); then
                        NEW_TIMESTAMP="$PREV_TIMESTAMP"
                        NEW_TZ="$PREV_TZ"
                    fi
                    read PREV_TIMESTAMP PREV_TZ <<<$(git log -1 --pretty=format:%cd --date=raw "$merge_source")
                    if (($NEW_TIMESTAMP < $PREV_TIMESTAMP)); then
                        NEW_TIMESTAMP="$PREV_TIMESTAMP"
                        NEW_TZ="$PREV_TZ"
                    fi
                    export GIT_AUTHOR_DATE="$NEW_TIMESTAMP $NEW_TZ"
                    export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
                    if [ -n "$merge_cherry" ]; then
                        run git cherry-pick $(git rev-list --min-parents=2 --max-count=1 "$merge_source")..$merge_source
                    elif [ -n "$RESET" ]; then # skip merges if not resetting
                        if [ -n "$merge_log" ]; then
                            run git merge --no-ff --no-edit "$merge_source" -m "$merge_log" || git commit --no-edit
                        else
                            run git merge --no-ff --no-edit "$merge_source" || git commit --no-edit
                        fi
                    fi
                    unset GIT_AUTHOR_DATE
                    unset GIT_COMMITTER_DATE
                done

            run meta-write "refs/heads/pr/$want/.export" "refs/heads/$BRANCH"
        elif [ -n "$merge" ]; then
            echo "Error: ignoring merge list '$merge' since not first commit of pr"
        fi

        local patch

        echo PREPTACH ~/src/meta/refs/heads/pr/"$want"/.prepatch-"$desc*"
        for patch in ~/src/meta/refs/heads/pr/"$want"/.prepatch-"$desc"*; do
            if [ -f "$patch" ] && [ -z "$fixup" ]; then
                run git apply --index -3 --verbose "$patch"
                patched[$patch]=1
            fi
        done

        # Based on https://github.com/dingram/git-scripts/blob/master/scripts/git-cherry-pick-with-committer
        local metacommit=$COMMIT
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

        local scr=$(script-get "$COMMIT")
        if [ -z "$scr" ]; then
        # Try to push past failure. Useful with:
        #   git config --global rerere.enabled true
        #   git config --global rerere.autoupdate true
           run git cherry-pick --no-commit "$COMMIT" || git diff --exit-code
        else
           run bash -c "$scr"
           git add -u
        fi

        if [ -e "$(git rev-parse --git-dir)/index.lock" ]; then
            echo "(((((((((((sleep to avoid index.lock fs race)))))))))))"
            sleep 1
        fi

        local patch
        for patch in ~/src/meta/refs/heads/pr/"$want"/.postpatch-"$desc"*; do
            if [ -f "$patch" ]; then
                run git apply --index -3 --verbose "$patch"
                patched[$patch]=1
            fi
        done

        local fix=
        if [ -n "$fixup" ]; then
            fix="fixup! $rest"$'\n'$'\n'
        fi
        if [ -n "$revert" ]; then
            fix="Revert \"$rest"$'\n'$'\n'
        fi
        if [ -n "$squash_next" ]; then
            true
        elif [ -n "$squash" ]; then
            # Skip squash into previous if no previous commits (unless resetting)
            if [ -n "$committed" -o -n "$RESET" ]; then
                run git commit --amend --no-edit
            fi
        else
            run git commit -m"$fix$(git log -1 --pretty=format:%b $COMMIT)"
            committed=1
        fi
        unset GIT_AUTHOR_NAME
        unset GIT_AUTHOR_EMAIL
        unset GIT_AUTHOR_DATE
        unset GIT_COMMITTER_NAME
        unset GIT_COMMITTER_EMAIL
        unset GIT_COMMITTER_DATE

        if [ -n "$scr" ]; then
            run script-check HEAD
            run git checkout "pr/$want"
        fi

        if [[ $rest == *"SPECIAL"* ]]; then
            run make -j12
        fi
    done < <(git log --format=format:'%H %s' --reverse "$SPAN" && echo)
    run git checkout $BRANCH
    echo "== Successfully exported branch pr/$want =="
    echo "ppush pr/$want"

    local patch
    for patch in ~/src/meta/refs/heads/pr/"$want"/.{pre,post}patch-*; do
        if [ -f "$patch" -a -z "${patched[$patch]}" ]; then
            echo "Warning: ignored patch $patch"
        fi
    done
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
    git log --format=format:'%H %s' --reverse "$SPAN"
    exit 0
fi

git-isclean.sh || exit 1

update "$@"
