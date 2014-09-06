#!/bin/bash
set -x
set -e

B="$(git rev-parse --show-cdup)BASE"
git rebase $(git rev-list -n1 HEAD -- "$B")^ --onto "$(<"$B")"
