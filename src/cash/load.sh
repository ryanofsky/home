#!/bin/bash

set -e
set -x

test ! -e russ.db || rm -iv russ.db
sqlite3 russ.db < russ.db.sql
