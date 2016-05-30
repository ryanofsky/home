#!/bin/bash

find -name '*.upstream' -printf '%P\n' | sort | while read u; do
    n="${u%.upstream}"
    echo diff -u $u $n
    diff -u $u $n
done | colordiff | less -F -X
