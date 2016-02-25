#!/bin/bash

set -e
set -x

port=$($(dirname "$0")/port_forward.sh | sed -n 's/^{"port":\([0-9]\+\)}$/\1/p')

cp -avf .aMule/amule.conf{,.prev}

# http://stackoverflow.com/questions/16987648/update-var-in-ini-file-using-bash
sed -i '/^\[eMule\]$/,/^\[/ s/^\(Port=\).*/\1'"$port"'/' .aMule/amule.conf
diff -u .aMule/amule.conf{.prev,} || true
rm -v .aMule/amule.conf.prev
exec amule
