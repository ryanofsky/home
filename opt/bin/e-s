#!/bin/bash

#ssh -R 17873:localhost:17873 -N g
socat TCP-L:17873,fork,reuseaddr - | while read LINE; do emacsclient -n "/scpx:g:$LINE"; done
