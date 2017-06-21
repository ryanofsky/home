# Get branch name
getname() {
  if [ -n "$1" ]; then
    echo "$1"
  else
    git symbolic-ref --short HEAD
  fi
}

# Get latest existing tag number for passed branch
getnum() {
  git for-each-ref --format='%(refname:short)' "$@" | {
    local NMAX=
    while read REF; do
      local N="${REF#*.}"
      local N="${N%%.*}"
      if [ -z "$NMAX" ] || [ "$N" -gt "$NMAX" ]; then
        NMAX="$N"
      fi
    done
    echo "$NMAX"
  }
}

# Associate PR name with PR number
set-pr() {
  local name="$1"
  local num="$2"
  git config branch."$name".prbranch "origin/pr/$num"
  git config branch."origin/pr/$num".prlocal "$name"
}

get-pr() {
    local pr="$1"
    if [[ "$pr" =~ ^[0-9]*$ ]]; then
        git config branch."origin/$pr".prlocal
    else
        git config branch."$pr".prbranch
    fi
}

# Dump PR patchsets for comparison
dump-pr() {
  local name="$1"
  local branch="pr/$name"
  local prbranch="$(git config branch.$branch.prbranch)"
  local exbranch="${2:-export}"
  local basebranch=origin/master

  echo "== $branch / $prbranch / $exbranch =="
  rm -rvf dump-$name-{branch,prbranch,exbranch}
  git format-patch --numbered-files -o dump-$name-branch $(git merge-base $basebranch $branch)..$branch
  git format-patch --numbered-files -o dump-$name-prbranch $(git merge-base $basebranch $prbranch)..$prbranch

  mkdir dump-$name-exbranch
  local lcommit
  local lname
  i=0
  while read lcommit lname rest; do
    if [ "$name" = "$lname" ]; then
      ((++i))
      git format-patch -n1 --numbered-files --start-number="$i" -o dump-$name-exbranch "$lcommit"
    fi
  done < <(git log --format=format:'%H %s%n' --reverse $(git merge-base $basebranch $exbranch)..$exbranch && echo)

  diff -rNu dump-$name-{exbranch,branch}
}

# Create directory with individual patch files and overall diff
# dump-patch d1
# dump-patch d2 fecd
# dump-patch r0 HEAD 3
dump-patch() {
    local dir="$1"
    local rev="${2:-HEAD}"
    local n="$3"
    if [ -z "$3" ]; then
        git format-patch -o "$dir" $(git merge-base origin/master "$rev").."$rev"
        git diff $(git merge-base origin/master "$rev").."$rev" > "$dir/diff"
    else
        git format-patch -o "$dir" -n"$n" "$rev"
        git diff "$rev~$n..$rev" > "$dir/diff"
    fi
}

pdiff() {
    diff -ru -I "^@@.*" -I "^index " -I "^From " "$@" | cdiff
}

# Print commands for pulling commits from PR branch to export branch
pull-pr() {
  local name="$1"
  local branch="pr/$name"
  local basebranch=origin/master
  local subj="$name"
  local lcommit
  for lcommit in $(git rev-list --reverse $(git merge-base $basebranch $branch)..$branch); do
    echo git cherry-pick "$lcommit"
    echo add-subj "\"$subj\""
    subj="$name $name"
  done
}

# Add export-branch subject line to HEAD commit
add-subj() {
  GIT_EDITOR="sed -i '1 s/.*/$@ # &\n\n&/g'" git commit --amend
}

ntag() {
    local name
    if [ -n "$1" ]; then
        name="$1"
    else
        name=$(getname)
        if [ -z "$name" ]; then
            echo No current branch
            return 1
        fi
    fi

    local bname=
    local wname=
    local ename=
    local suf=${name##*-}
    local pref=
    if [ "$suf" = work ]; then
        pref="${name%work}"
    elif [ "$suf" = base ]; then
        pref="${name%base}"
    elif [ "$suf" = export ]; then
        pref="${name%export}"
    else
        suf=
    fi
    if [ -n "$suf" ]; then
        bname="${pref}base"
        wname="${pref}work"
        ename="${pref}export"
        prev=$(getnum "refs/tags/$bname.*" "refs/tags/$wname.*" "refs/tags/$ename.*")
        echo "bname=$bname wname=$wname ename=$ename prev=$prev"
        if ! git diff --quiet "$wname..$ename"; then
            echo "Error: differences found in $wname..$ename"
            return 1
        fi
        if [ "$(git merge-base "$bname" "$wname")" != "$(git rev-parse $bname)" ]; then
           echo "Error: incompatible base branch $bname for work branch $wname"
           return 1
        fi
        if [ "$(git merge-base "$bname" "$ename")" != "$(git rev-parse $bname)" ]; then
            echo "Error: incompatible base branch $bname for work branch $ename"
            return 1
        fi
        if [ "$(git rev-parse "$bname")" = "$(git rev-parse "$bname.$prev")" -a \
             "$(git rev-parse "$wname")" = "$(git rev-parse "$wname.$prev")" -a \
             "$(git rev-parse "$ename")" = "$(git rev-parse "$ename.$prev")" ]; then
            echo "No changes ($bname = $bname.$prev = $(git rev-parse "$bname"))"
            echo "No changes ($wname = $wname.$prev = $(git rev-parse "$wname"))"
            echo "No changes ($ename = $ename.$prev = $(git rev-parse "$ename"))"
            return 1
        fi
        echo git tag "$bname.$((prev+1))" "$bname"
        echo git tag "$wname.$((prev+1))" "$wname"
        echo git tag "$ename.$((prev+1))" "$ename"
        return 0
    fi

    local prev=$(getnum "refs/tags/$name.*")
    if [ -n "$prev" ]; then
        if [ "$(git rev-parse "$name")" = "$(git rev-parse "$name.$prev")" ]; then
            echo "No changes ($name = $name.$prev = $(git rev-parse "$name"))"
            return 1
        fi
    fi
    echo git tag "$name.$((prev+1))" "$name"
}

ppush() {
    local name
    if [ -n "$1" ]; then
        name="$1"
    else
        name=$(getname)
        if [ -z "$name" ]; then
            echo No current branch
            return 1
        fi
    fi
    local cur=$(getnum "refs/tags/$name.*")
    if [ "$(git rev-parse "$name")" != "$(git rev-parse "$name.$cur")" ]; then
      cur="$((cur+1))"
    fi
    local prev
    if [ -n "$2" ]; then
        prev="$2"
    else
        prev="$((cur-1))"
    fi

    ntag "$name"
    echo git push -u russ $name.$cur +$name
    echo

    local prbranch="$(git config branch.$name.prbranch)"
    if [ -z "$prbranch" ]; then
        echo "Open https://github.com/ryanofsky/bitcoin/pull/new/$name"
        echo "set-pr $name ###"
        local base2=$(git rev-list --min-parents=2 --max-count=1 "$name")
    else
        echo "Pull https://github.com/bitcoin/bitcoin/pull/${prbranch#origin/pr/}"
        echo

        local b1="$name.$prev"
        local b2="$name.$cur"
        local u="https://github.com/ryanofsky/bitcoin/commits"
        local c="https://github.com/ryanofsky/bitcoin/compare/$b1...$b2"
        local r="$(git rev-parse "$b1") -> $(git rev-parse "$name")"
        local b="[$b1]($u/$b1) -> [$b2]($u/$b2)"

        local base1=$(git rev-list --min-parents=2 --max-count=1 "$b1")
        local base2=$(git rev-list --min-parents=2 --max-count=1 "$name")
        if [ "$base1" = "$base2" ]; then
            if [ "$(git merge-base "$b1" "$name")" = "$(git rev-parse "$b1")" ]; then
                echo "Added $(git rev-list "$b1..$name" | wc -l) commits $r ($b, [compare]($c))"
            elif git diff --quiet "$b1".."$name"; then
                echo "Squashed $r ($b)"
            else
                echo "Updated $r ($b)"
            fi
        else
            echo "Rebased $r ($b)"
        fi
    fi
        echo

        local master="$(git merge-base "$base2" origin/master)"
        if [ "$base2" != "$master" ]; then
            local bases=
            local subj
            while read subj; do
                local bb=$(sed "s/Merge branch '\([^']\+\)' into.*/\1/" <<<"$subj")
                local bp=$(get-pr "$bb")
                if [ -n "$bases" ]; then
                    bases="$bases + "
                fi
                if [ -n "$bp" ]; then
                    bases="$bases#${bp#origin/pr/}"
                else
                    bases="$bases$bb"
                fi
            done < <(git log --reverse --min-parents=2 --format=format:'%s' $master..$base2 && echo)

            echo "**This is based on $bases.** The non-base commits are:"
        else
            echo "Commits:"
        fi
        echo

    if [ -n "$prbranch" ]; then
        git log --reverse $base2..$name --format=format:'- [`%h` %s](https://github.com/bitcoin/bitcoin/pull/'"${prbranch#origin/pr/}"'/commits/%H)'
    else
        git log --reverse $base2..$name --format=format:'- %H %s'
    fi
}
