#!/usr/bin/env bash

set -x
set -e

if test -e out.wav; then
  echo Error: out.wav exists
  exit 1
fi

arecord --device=hw:CARD=Device,DEV=0 --format=S16_LE --channels=2 --rate=48000 --vumeter=stereo out.wav
