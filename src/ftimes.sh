#!/usr/bin/env bash

# http://www.commandlinefu.com/commands/view/5720/find-files-and-list-them-sorted-by-modification-time

find -type f -print0 | xargs -r0 stat -c %y\ %n | sort
