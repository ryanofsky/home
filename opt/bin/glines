#!/bin/bash

# sudo pip install hungarian
# cd opt/src
# git clone https://github.com/trast/tbdiff.git
# ln -sv $HOME/opt/src/tbdiff/git-tbdiff.py $HOME/opt/bin/git-tbdiff

ds() {
 read LINE
 INS=$(sed -n 's/.*, \([0-9]\+\) insertion.*/\1/p'  <<< "$LINE")
 DEL=$(sed -n 's/.*, \([0-9]\+\) deletion.*/\1/p' <<< "$LINE")
 echo "(+${INS:-0}/-${DEL:-0})"
}

if [ -n "$3" ]; then
  declare -A COUNTS
  while read -r LINE; do
    if [[ "$LINE" =~ ^([0-9]+)(\ \ \ \ \ (.*))?$ ]]; then
      COUNT="${BASH_REMATCH[1]}"
      PATTERN="t$(echo "${BASH_REMATCH[3]}" | tr ' +-' 'spm')"
      COUNTS[$PATTERN]="$COUNT"
    else
      echo "Interdiff Error" 1>&2
      exit 1
    fi
  done < <(git tbdiff --no-color ${1}..${2} ${3}..${4} | grep -o '^    [-+ ][-+ ]' | sort | uniq -c)
  LINES="(+$(( ${COUNTS[tsm]:-0} + ${COUNTS[tsp]:-0} + ${COUNTS[tmp]:-0} ))/-$(( ${COUNTS[tm]:-0} + ${COUNTS[tp]:-0} + ${COUNTS[tpm]:-0} )))"
  echo "$LINES"
  #echo "$LINES - git tbdiff ${1}..${2} ${3}..${4}" 1>&2
elif [ -n "$2" ]; then
  git diff "${1}..${2}" | diffstat -s | ds
else
  git diff "${1}^..${1}" | diffstat -s | ds
fi 
