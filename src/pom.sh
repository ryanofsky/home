#!/bin/bash

T=${1:-25m}
for i in {1..10}; do
  echo $(date) -- +$T
  sleep $T
  e -c $(readlink -f "$HOME/.ln/todo.org")
  T=5m
done
