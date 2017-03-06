#!/bin/bash

T=${1:-25m}
while true; do
  echo $(date) -- +$T
  sleep $T
  e -c $(readlink -f "$HOME/.ln/todo.org")
  T=5m
done
