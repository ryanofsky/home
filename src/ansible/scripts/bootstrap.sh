#!/bin/bash

set -x

cryptsetup --verbose --batch-mode luksFormat /dev/xvdb <<<"$LUKSPASS"
