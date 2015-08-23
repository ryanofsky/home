#!/bin/bash

if ! git diff --quiet --cached; then
  echo "Error: uncommitted staged changes."  >&2
  exit 1
fi

if ! git diff --quiet; then
  echo "Error: uncommitted unstaged changes." >&2
  exit 1
fi

exit 0
