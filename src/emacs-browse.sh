#!/usr/bin/env bash

#ssh -Y gl "/opt/google/chrome/chrome" $(printf "%q" "$1")
#ssh gv DISPLAY=:0 firefox $(printf "%q" "$1")
#ssh gl DISPLAY=:0 google-chrome-stable $(printf "%q" "$1")
#ssh gv DISPLAY=:0 google-chrome-stable $(printf "%q" "$1")
google-chrome-stable "$@"
