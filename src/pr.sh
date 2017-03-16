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
  local NAME="$1"
  git for-each-ref --format='%(refname:short)' \
      "refs/tags/$NAME.*" | {
    NMAX=0
    while read REF; do
      local N="${REF#*.}"
      local N="${N%%.*}"
      if [ "$N" -gt "$NMAX" ]; then
        NMAX="$N"
      fi
    done
    echo "$NMAX"
  }
}

# Print squash/rebased message for branch
pmsg() {
  local b="$1"
  local n="$2"
  local squash="$3"
  local b1="$b.$((n-1))"
  local b2="$b.$n"
  local u="https://github.com/ryanofsky/bitcoin/commits"
  local c="https://github.com/ryanofsky/bitcoin/compare/$b1...$b2"

  local r="$(git rev-parse "$b1") -> $(git rev-parse "$b2")"
  local b="[$b1]($u/$b1) -> [$b2]($u/$b2)"
  if [ -n "$squash" ]; then
    echo "Squashed $r ($b, [compare]($c))"
  else
    echo "Rebased $r ($b)"
  fi

  local prbranch="$(git config branch.$1.prbranch)"
  echo https://github.com/bitcoin/bitcoin/pull/${prbranch#origin/pr/}
}

# Print commands for tagging and pushing current checked out PR
ppush() {
  local name=$(getname)
  local max=$(getnum "$name")
  local prev="$name.$max"
  local next="$name.$((max+1))"
  if [ "$(git rev-parse "$prev")" = \
       "$(git rev-parse "$name")" ]; then
    echo "Not saving: no changes found."
    return 0
  fi
  local name=$(getname)
  local max=$(getnum "$name")
  echo git tag "$next" "$name"
  echo git push -u russ "$next" "$name"
  echo git push -u russ --force "$next" "$name"
  echo pmsg "$name" "$((max+1))"
}

# Print commands for squashing current checked out PR
psquash() {
  local name=$(getname)
  echo "git rebase -i --autosquash \$(git merge-base origin/master $name) $name"
  echo ppush
}

# Associate PR name with PR number
set-pr() {
  local name="$1"
  local num="$2"
  git config branch."pr/$name".prbranch "origin/pr/$num"
  git config branch."origin/pr/$num".prlocal "pr/$name"
}

# Dump PR patchsets for comparison
dump-pr() {
  local name="$1"
  local branch="pr/$name"
  local prbranch="$(git config branch.$branch.prbranch)"
  local exbranch=export
  local basebranch=origin/master

  echo "== $branch / $prbranch / $exbranch =="
  rm -rvf dump-$name-{branch,prbranch,exbranch}
  git format-patch --numbered-files -o dump-$name-branch $(git merge-base $basebranch $branch)..$branch
  git format-patch --numbered-files -o dump-$name-prbranch $(git merge-base $basebranch $prbranch)..$prbranch

  mkdir dump-$name-exbranch
  local lcommit
  local lname
  i=0
  while read lcommit lname; do
    if [ "$name" = "$lname" ]; then
      ((++i))
      git format-patch -n1 --numbered-files --start-number="$i" -o dump-$name-exbranch "$lcommit"
    fi
  done < <(git log --format=format:'%H %s' --reverse $(git merge-base $basebranch $exbranch)..$exbranch)

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
