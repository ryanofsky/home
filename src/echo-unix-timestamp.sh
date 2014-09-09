#!/bin/bash
date -d @$(($1 / 1000)) +%c
