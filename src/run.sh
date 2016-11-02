#!/bin/bash

space=""
for arg in "$@"; do
  printf "$space%q" "$arg" 1>&2
  space=" "
done
printf "\n" 1>&2
"$@"
