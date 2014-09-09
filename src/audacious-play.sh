#!/bin/bash

cat | tr '\n' '\0' | xargs -0 -n1 audacious -e