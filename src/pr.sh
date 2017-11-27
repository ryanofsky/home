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
      local N="${REF##*.}"
      if [ -z "$NMAX" ] || [ "$N" -gt "$NMAX" ] 2>/dev/null; then
        NMAX="$N"
      fi
    done
    echo "$NMAX"
  }
}

# Write meta value
meta-write() {
    local name=$1
    local value=$2
    if [ "$name" != "${name%/*}" ]; then
       mkdir -p "$HOME/src/meta/${name%/*}"
    fi
    echo "$value" > "$HOME/src/meta/$name"
    (cd "$HOME/src/meta" && git add "$name")
    echo "write $name $value" >> $HOME/src/meta/log
}

# Read meta value
meta-read() {
    local name="$1"
    cat "$HOME/src/meta/$name"
}

# Associate PR name with PR number
set-pr() {
  local name="$1"
  local num="$2"
  local rname="refs/heads/$name"
  local rnum="refs/remotes/origin/pull/$num/head"
  meta-write "$rname/.prbranch" "$rnum"
  meta-write "$rnum/.prlocal" "$rname"
}

# map pr/name to number and vice versa
get-pr() {
    local pr="$1"
    if [[ "$pr" =~ ^[0-9]*$ ]]; then
        local rnum="refs/remotes/origin/pull/$pr/head"
        meta-read "$rnum/.prlocal"
    else
        local rname="refs/heads/$pr"
        meta-read "$rname/.prbranch" | sed 's:refs/remotes/origin/pull/\(.*\)/head:\1:'
    fi
}

# Dump PR patchsets for comparison
dump-pr() {
  local name="$1"
  local branch="pr/$name"
  local rname="refs/heads/$branch"
  local prbranch="$(meta-read "$rname/.prbranch" | sed 's:refs/remotes/:')"
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
        local pad=$((- ${#bname} - ${#prev} - 1))
        printf "%*s %s   %*s %s   %*s %s\n" $pad "$wname" "$(git rev-parse --short "$wname")" $(($pad - 2)) "$ename" "$(git rev-parse --short "$ename")" $pad "$bname" "$(git rev-parse --short "$bname")"
        printf "%*s %s   %*s %s   %*s %s\n" $pad "$wname.$prev" "$(git rev-parse --short "$wname.$prev")" $(($pad - 2)) "$ename.$prev" "$(git rev-parse --short "$ename.$prev")" $pad "$bname.$prev" "$(git rev-parse --short "$bname.$prev")"

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
             "(" "$(git rev-parse "$wname")" = "$(git rev-parse "$wname.$prev")" -o \
                 "$(git rev-parse "$wname")" = "$(git rev-parse "$ename.$prev")" ")" -a \
             "$(git rev-parse "$ename")" = "$(git rev-parse "$ename.$prev")" ]; then
            echo "No changes ($bname = $bname.$prev = $(git rev-parse "$bname"))"
            echo "No changes ($ename = $ename.$prev = $(git rev-parse "$ename"))"
            if [ "$(git rev-parse "$wname")" = "$(git rev-parse "$ename.$prev")" ]; then
                echo "No changes ($wname = $ename.$prev = $(git rev-parse "$wname"))"
            elif [ "$(git rev-parse "$wname")" = "$(git rev-parse "$wname.$prev")" ]; then
                echo "No changes ($wname = $wname.$prev = $(git rev-parse "$wname"))"
                echo "git-isclean.sh && git checkout $wname && git reset --hard $ename"
            else
                echo "Unexpected"
                return 1
            fi
            echo "git-isclean.sh && git checkout $bname && git reset --hard origin/master"
            echo "git-isclean.sh && git rebase -i $bname $ename"
            echo "git-isclean.sh && git checkout $wname && git reset --hard $ename"
        else
            echo git tag "$bname.$((prev+1))" "$bname"
            echo git tag "$wname.$((prev+1))" "$wname"
            echo git tag "$ename.$((prev+1))" "$ename"
        fi
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
    local descpath="$HOME/src/meta/refs/heads/$name/.prdesc.md"
    local prnum="$(get-pr "$name")"
    if [ -z "$prnum" ]; then
        local base2=$(git rev-list --min-parents=2 --max-count=1 "$name" --)
    else
        local b1="$name.$prev"
        local b2="$name.$cur"
        local u="https://github.com/ryanofsky/bitcoin/commits"
        local c="https://github.com/ryanofsky/bitcoin/compare/$b1...$b2"
        local r="$(git rev-parse "$b1") -> $(git rev-parse "$name")"
        local b="[$b1]($u/$b1) -> [$b2]($u/$b2)"
        local base1=$(git rev-list --min-parents=2 --max-count=1 "$b1")
        local base2=$(git rev-list --min-parents=2 --max-count=1 "$name" --)
    fi

    echo "== Tag and push =="
    ntag "$name"
    echo git push -u russ $name.$cur +$name
    echo

    echo "== Update =="
    echo "git checkout $(meta-read refs/heads/$name/.export)"
    echo "pr ${name#pr/}"
    echo "set-pr $name ${prnum:-###}"
    echo "vi $descpath"
    if [ -n "$prnum" ]; then
        echo "https://github.com/bitcoin/bitcoin/pull/$prnum"
    fi
    echo "https://github.com/ryanofsky/bitcoin/pull/new/$name"
    echo "https://github.com/ryanofsky/bitcoin/commits/$name"
    echo

    if [ -n "$prnum" ]; then
        echo "== Comment =="
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

        echo "== Description =="
        local desc=$(cat "$descpath" 2>/dev/null || true)
        if [ -n "$desc" ]; then
          local commits=$(git log --reverse $base2..$name --format=format:'[`%h` %s](https://github.com/bitcoin/bitcoin/pull/'"$prnum"'/commits/%H)')
          python3 -c '
import sys

class Commits:
    def __init__(self, commits):
        self.commits = commits.split("\n")

    def __format__(self, spec):
        for commit in self.commits:
           if spec in commit:
               return commit
        raise Exception("No commit {!r}".format(spec))

print(sys.argv[1].format(commit=Commits(sys.argv[2])))' "$desc" "$commits"
          echo
        fi

        local master="$(git merge-base "$base2" origin/master)"
        if [ "$base2" != "$master" ]; then
            local bases=
            local subj
            while read subj; do
                local bb=$(sed "s/Merge branch '\([^']\+\)' into.*/\1/" <<<"$subj")
                local bb=$(sed "s:Merge remote-tracking branch 'origin/pull/\([^']\+\)/head':\1:" <<<"$bb")
                local bp=$(get-pr "$bb")
                if [ -n "$bases" ]; then
                    bases="$bases + "
                fi
                bases="$bases#${bb}"
            done < <(git log --reverse --min-parents=2 --format=format:'%s' $master..$base2 && echo)

            echo "**This is based on $bases.** The non-base commits are:"
        else
            echo "Commits:"
        fi
        echo

    if [ -n "$prnum" ]; then
        git log --reverse $base2..$name --format=format:'- [`%h` %s](https://github.com/bitcoin/bitcoin/pull/'"$prnum"'/commits/%H)'
    else
        git log --reverse $base2..$name --format=format:'- %H %s'
    fi
}

pr-merge() {
    local branch="origin/pull/$1/head"
    export GIT_AUTHOR_DATE="$(git log -1 --pretty=format:%ad "$branch" --date=raw)"
    export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
    git merge --no-ff --no-edit -m "Merge remote-tracking branch '$branch'" "$branch"
}

pr-rev() {
    local branch="origin/pull/$1/head"
    local tag="review.$1"
    local num=$(getnum "refs/tags/$tag.*")
    local new=$(git rev-parse "$branch")
    local t
    declare -A seen
    for t in $(git reflog "origin/pull/$1/head" --format='%gd' | tac) $(git for-each-ref --format='%(refname:short)' "refs/tags/$tag.*"); do
      local r=$(git rev-parse --short "$t")
      if [ -n "${seen[$r]}" ]; then
         continue
      fi
      seen[$r]=1
      local b=$(git merge-base "$t" origin/master)
      local bs=$(git rev-parse --short "$b")
      local c=$(git rev-list "$b..$t" | wc -l)
      local d=$(git diff --shortstat "$b..$t")
      local rs=$(git rev-parse --short "$t")
      local m=$(git log -n1 --pretty=format:"%cI" "$t")
      local ts=$(git log -n1 --pretty=format:%D "$t")
      if [[ "$ts" != *"$t"* ]]; then
        ts="$t $ts"
      fi
      echo "- $(tput setaf 2)$m, $(tput setaf 3)$rs base $bs, $(tput setaf 2)$(tput bold)$ts$(tput sgr0)"
      echo "  $c commits,$d"
    done
    if [ -z "$new" ]; then
        echo "Branch '$branch' doesn't exist."
        return 1
    elif [ -n "$num" ] && [ "$new" = "$(git rev-parse "$tag.$num")" ]; then
        echo "No changes: $branch == $tag.$num == $new"
    else
        num=$((num + 1))
        echo git tag "$tag.$num" "$branch"
    fi
    if [ "$num" -gt 1 ]; then
        echo rm -rvf "_$((num-1))" "_$((num))"
        echo dump-patch "_$((num-1))" "$tag.$((num-1))"
        echo dump-patch "_$((num))" "$tag.$((num))"
        echo "diff -ru -I'^index ' -I'^@@' _$((num-1)) _$((num)) | cdiff"
        echo meld "_$((num-1))" "_$((num))"
    fi
    echo utACK "$new"
}

log-find() {
  git log --grep="$1" --all --source
}

check-branch() {
    local branch="$1"
    local ctx="$2"
    if ! git rev-parse --quiet --verify "$branch" >/dev/null; then
        echo "Error: bad branch '$branch'$ctx"
    fi
}

pad() {
    printf "%*s" "-$1" "$2"
}

brev() {
    echo "$1" | sed -e 's:refs/heads/::' -e 's:refs/remotes/origin/pull/\([^/]\+\)/head:#\1:' -e 's:refs/remotes/\([^\/]\+\)/pull/\([^/]\+\)/head:\1#\2:' -e 's:refs/remotes/::'
}

pr-list() {
    local red=$(tput setaf 1)
    local green=$(tput setaf 2)
    local reset=$(tput sgr0)

    local f
    find ~/src/meta -type f -printf '%P\n' | while read f; do
        if [ "$f" = .git -o "$f" = "log" ]; then
            continue
        fi
        local branch=${f%/*}
        local attrib=${f##*/}
        check-branch "$branch" " for '$f'"
        if [ "$attrib" = .export ]; then
            check-branch "$(cat ~/src/meta/"$f")" " in '$f'"
        elif [ "$attrib" = .abandon ]; then
            local abandon=$(cat ~/src/meta/"$f")
            if [ ! -f ~/src/meta/"$f" -o -s ~/src/meta/"$f" ]; then
                echo "Error: bad '$f' is not an empty file"
            fi
        elif [ "$attrib" = .prbranch ]; then
            local rbranch=$(cat ~/src/meta/"$f")
            local lbranch=$(cat ~/src/meta/"$rbranch"/.prlocal)
            if [ "$branch" != "$lbranch" ]; then
                echo "Error: bad '$lbranch/.prlocal' found '$lbranch' expected '$branch' from '$f'"
            fi
        elif [ "$attrib" = .prlocal ]; then
            local lbranch=$(cat ~/src/meta/"$f")
            local rbranch=$(cat ~/src/meta/"$lbranch"/.prbranch)
            if [ "$branch" != "$rbranch" ]; then
                echo "Error: bad '$lbranch/.prbranch' found '$rbranch' expected '$branch' from '$f'"
            fi
            check-branch "$(cat ~/src/meta/"$f")" " in '$f'"
        elif [ "$attrib" = .prdest ]; then
            check-branch "$(cat ~/src/meta/"$f")" " in '$f'"
        elif [ "$attrib" = .prbase ]; then
            check-branch "$(cat ~/src/meta/"$f")" " in '$f'"
        elif [ "$attrib" = .prdesc.md ]; then
            true
        else
            echo "Error: unknown attribute '$attrib' for '$f'"
        fi
    done

    git for-each-ref --format='%(refname:short)' 'refs/heads/pr/*' | while read name; do
        local show_all=
        if [ "$#" -gt 0 ]; then
          local arg=
          local found=
          local filter=
          for arg in "$@"; do
              if [ "$arg" = "-a" ]; then
                  show_all=1
              else
                  filter=1
                  if [[ "$name" == *"$arg"* ]]; then
                    found=1;
                    continue;
                  fi
              fi
          done
          if [ -n "$filter" -a -z "$found" ]; then continue; fi
        fi
        local dest=refs/remotes/origin/master
        if [ -e "$HOME/src/meta/refs/heads/$name/.abandon" ]; then
            dest=""
        fi
        if [ -e "$HOME/src/meta/refs/heads/$name/.prdest" ]; then
            if [ -z "$dest" ]; then
                echo "Error: replaced '$name' marked abandoned"
            fi
            dest=$(cat "$HOME/src/meta/refs/heads/$name/.prdest")
        fi

        local prbase=
        if [ -e "$HOME/src/meta/refs/heads/$name/.prbase" ]; then
            prbase=$(cat "$HOME/src/meta/refs/heads/$name/.prbase")
        fi

        local prbranch=
        if [ -e "$HOME/src/meta/refs/heads/$name/.prbranch" ]; then
            prbranch=$(cat "$HOME/src/meta/refs/heads/$name/.prbranch")
            if [ -n "$prbase" ]; then
                echo "Error: branch '$name' conflicting prbase '$prbase' prbranch '$prbranch'"
            fi
        fi

        local src="$prbase"
        if [ -e "$HOME/src/meta/refs/heads/$name/.export" ]; then
            src=$(cat "$HOME/src/meta/refs/heads/$name/.export")
            if [ -n "$prbase" ]; then
                echo "Error: branch '$name' conflicting prbase '$prbase' src '$src'"
            fi
        fi

        local state=unmerged
        if [ -z "$dest" ]; then
            state=abandoned
            if [ -z "$show_all" ]; then continue; fi
        else
            local base=$(git merge-base "$name" "$dest")
            local hash=$(git rev-parse "$name")
            if [ "$hash" = "$base" ]; then
                if [ -z "$show_all" ]; then continue; fi
                state=merged
            else
                GIT_INDEX_FILE=/tmp/oindex git read-tree "$dest"
                if ! git diff "$base".."$hash" | GIT_INDEX_FILE=/tmp/oindex git apply --cached --check 2>/dev/null; then
                    state=conflicted
                fi
            fi
            if [ -n "$prbranch" ]; then
                if [ "$(git rev-parse "$prbranch")" != "$hash" ]; then
                    echo "Error: branch '$name' doesn't match upstream '$prbranch'"
                fi
            fi
        fi

        local tag="$name"
        local cur=$(getnum "refs/tags/$name.*")
        if [ -n "$cur" ]; then
           if [ "$hash" != "$(git rev-parse "$name.$cur")" ]; then
               tag="$tag$red.$cur$reset"
           else
               tag="$tag$green.$cur$reset"
           fi
        else
            tag="$tag$green$reset"
        fi

        local out=
        out=$(pad 40 "$tag")
        out=$(pad 60 "$out $(brev "$src")")
        out=$(pad 80 "$out $(brev "$prbranch")")
        out=$(pad 100 "$out $(brev "$dest")")
        out=$(pad 120 "$out $state")
        echo "$out"
    done
}
