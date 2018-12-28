#!/bin/bash

# called by dracut
check() {
    require_binaries intel_panel_fitter || return 1
    return 0
}

# called by dracut
depends() {
    return 0
}

# called by dracut
install() {
    inst_binary intel_panel_fitter
    inst_hook pre-trigger 01 "$moddir/intel-panel-fitter.sh"
}
